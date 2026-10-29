import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np
import pandas as pd
import yaml
from pymc_extras.prior import Prior
from pymc_marketing.mmm import GeometricAdstock, LogisticSaturation, MMM

from integrations.training.mmm.request import MMMRequest

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str, int, str], None]
MIN_ROWS = 20
MIN_CHANNEL_SPEND = 0.01
RHAT_LIMIT = 1.1
MODEL_FILE = "mmm_model.nc"
RHAT_VARIABLES = (
    "intercept_contribution",
    "y_sigma",
    "saturation_beta",
    "saturation_lam",
    "adstock_alpha",
    "gamma_control",
    "gamma_fourier",
)


def _prior(spec: dict[str, Any], **overrides: Any) -> Prior:
    return Prior(spec["distribution"], **{**{k: v for k, v in spec.items() if k != "distribution"}, **overrides})


class MMMConfig:
    def __init__(self, config_path: Path):
        self.raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    @property
    def channels(self) -> list[str]:
        return list(self.raw["channels"])

    @property
    def controls(self) -> list[str]:
        return list(self.raw["controls"])

    @property
    def date_column(self) -> str:
        return self.raw["date_column"]

    @property
    def target_column(self) -> str:
        return self.raw["target_column"]

    def model_config(self, prior_sigma: np.ndarray) -> dict[str, Prior]:
        priors = self.raw["model"]["priors"]
        likelihood = priors["likelihood"]
        return {
            "intercept": _prior(priors["intercept"]),
            "saturation_lam": _prior(priors["saturation_lam"], dims="channel"),
            "adstock_alpha": _prior(priors["adstock_alpha"], dims="channel"),
            "gamma_control": _prior(priors["gamma_control"], dims="control"),
            "gamma_fourier": _prior(priors["gamma_fourier"]),
            "saturation_beta": _prior(priors["saturation_beta"], sigma=prior_sigma, dims="channel"),
            "likelihood": Prior(
                likelihood["distribution"],
                lower=likelihood["lower"],
                sigma=Prior(likelihood["sigma"]["distribution"], sigma=likelihood["sigma"]["sigma"]),
            ),
        }

    def sampling(self, chains: int | None, tune: int | None, draws: int | None) -> dict[str, Any]:
        base = self.raw["sampling"]
        params: dict[str, Any] = {
            "chains": chains or base["chains"],
            "tune": base["tune"] if tune is None else tune,
            "target_accept": base["target_accept"],
            "random_seed": base["random_seed"],
        }
        if draws is not None:
            params["draws"] = draws
        return params


def _fix_object_dtypes(idata: Any) -> None:
    for node in idata.subtree:
        dataset = node.to_dataset(inherit=False)
        converted = {
            name: var.astype(str)
            for name, var in {**dataset.coords, **dataset.data_vars}.items()
            if var.dtype == object
        }
        if converted:
            node.update(converted)


class MMMTrainer:
    def __init__(
        self,
        *,
        data_path: Path,
        config_path: Path,
        output_dir: Path,
        request: MMMRequest | None,
        progress: ProgressFn,
        chains: int | None = None,
        tune: int | None = None,
        draws: int | None = None,
    ):
        self.data_path = data_path
        self.output_dir = output_dir
        self.request = request
        self.progress = progress
        self.config = MMMConfig(config_path)
        self.sampling_overrides = (chains, tune, draws)
        self.model: MMM | None = None
        self.frame: pd.DataFrame | None = None
        self.channels: list[str] = []
        self.controls: list[str] = []
        self.excluded_channels: list[str] = []

    def run(self) -> dict[str, Any]:
        self.progress("loading_data", 5, "Loading the sample dataset")
        X, y, prior_sigma = self._prepare()
        self.progress("building_model", 15, f"Building the MMM with {len(self.channels)} channels")
        self._build(X, y, prior_sigma)
        sampling = self.config.sampling(*self.sampling_overrides)
        self.progress(
            "sampling",
            25,
            f"Sampling {sampling['chains']} chains after {sampling['tune']} tuning steps",
        )
        self._fit(X, y, sampling)
        divergences = self._divergences()
        max_rhat = self._max_rhat()
        self.progress("diagnostics", 85, f"{divergences} divergences, max R-hat {max_rhat:.3f}")
        if divergences == 0:
            self.progress("posterior_predictive", 90, "Sampling posterior predictive")
            self.model.sample_posterior_predictive(X, random_seed=np.random.default_rng(sampling["random_seed"]))
        path = self._save()
        self.progress("saving_model", 95, "Model saved locally")
        return {
            "status": "success",
            "model_path": str(path),
            "model_bytes": path.stat().st_size,
            "metrics": {
                "rows": len(self.frame),
                "date_start": self.frame[self.config.date_column].min().date().isoformat(),
                "date_end": self.frame[self.config.date_column].max().date().isoformat(),
                "channels": self.channels,
                "controls": self.controls,
                "excluded_channels": self.excluded_channels,
                "divergences": divergences,
                "max_rhat": round(max_rhat, 4),
            },
        }

    def _prepare(self) -> tuple[pd.DataFrame, pd.Series, np.ndarray]:
        frame = pd.read_csv(self.data_path)
        date_col = self.config.date_column
        target = self.config.target_column
        if date_col not in frame.columns or target not in frame.columns:
            raise ValueError(f"dataset must contain '{date_col}' and '{target}' columns")
        frame[date_col] = pd.to_datetime(frame[date_col])
        if self.request is not None:
            start = pd.Timestamp(self.request.date_start)
            end = pd.Timestamp(self.request.date_end)
            frame = frame[(frame[date_col] >= start) & (frame[date_col] <= end)]
        if len(frame) < MIN_ROWS:
            raise ValueError(f"need at least {MIN_ROWS} rows in the training window, found {len(frame)}")
        self.frame = frame.sort_values(date_col).reset_index(drop=True)

        requested = list(self.request.channels) if self.request else self.config.channels
        available = [c for c in requested if c in self.frame.columns]
        spend = self.frame[available].sum(axis=0)
        self.excluded_channels = sorted(spend[spend < MIN_CHANNEL_SPEND].index.tolist())
        self.channels = sorted(c for c in available if c not in self.excluded_channels)
        if not self.channels:
            raise ValueError("no channels with spend in the training window")
        self.controls = [c for c in self.config.controls if c in self.frame.columns]

        channel_spend = self.frame[self.channels].sum(axis=0)
        prior_sigma = (channel_spend / channel_spend.sum()).to_numpy()
        X = self.frame.drop(columns=target)
        y = self.frame[target]
        self.progress("loading_data", 10, f"Loaded {len(self.frame)} rows for {len(self.channels)} channels")
        return X, y, prior_sigma

    def _build(self, X: pd.DataFrame, y: pd.Series, prior_sigma: np.ndarray) -> None:
        params = self.config.raw["model"]
        self.model = MMM(
            date_column=self.config.date_column,
            channel_columns=self.channels,
            target_column=self.config.target_column,
            control_columns=self.controls,
            adstock=GeometricAdstock(l_max=params["adstock"]["l_max"]),
            saturation=LogisticSaturation(),
            time_varying_intercept=params["time_varying_intercept"],
            yearly_seasonality=params["yearly_seasonality"],
            model_config=self.config.model_config(prior_sigma),
            sampler_config={"progressbar": False},
        )
        self.model.build_model(X, y)
        self.model.add_original_scale_contribution_variable(
            var=[
                "channel_contribution",
                "control_contribution",
                "intercept_contribution",
                "yearly_seasonality_contribution",
                "y",
            ]
        )

    def _fit(self, X: pd.DataFrame, y: pd.Series, sampling: dict[str, Any]) -> None:
        extra = {"draws": sampling["draws"]} if "draws" in sampling else {}
        self.model.fit(
            X=X,
            y=y,
            chains=sampling["chains"],
            tune=sampling["tune"],
            target_accept=sampling["target_accept"],
            random_seed=np.random.default_rng(sampling["random_seed"]),
            **extra,
        )

    def _divergences(self) -> int:
        return int(self.model.idata.sample_stats.diverging.sum().item())

    def _max_rhat(self) -> float:
        posterior = self.model.idata.posterior
        names = [name for name in RHAT_VARIABLES if name in posterior.data_vars]
        summary = az.summary(data=self.model.idata, var_names=names)
        value = float(summary["r_hat"].max())
        if value > RHAT_LIMIT:
            logger.warning("max R-hat %.4f exceeds %.2f", value, RHAT_LIMIT)
        return value

    def _save(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / MODEL_FILE
        if path.exists():
            os.remove(path)
        _fix_object_dtypes(self.model.idata)
        self.model.save(str(path))
        return path

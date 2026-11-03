import argparse
import json
import logging
import sys
from pathlib import Path

from integrations.training.mmm.request import MMMRequest
from integrations.training.protocol import PROGRESS_PREFIX, RESULT_PREFIX, emit


def _progress(stage: str, percent: int, message: str) -> None:
    emit(PROGRESS_PREFIX, {"stage": stage, "percent": percent, "message": message})


def _request(raw: str | None) -> MMMRequest | None:
    if not raw:
        return None
    data = json.loads(raw)
    return MMMRequest(
        kpi=data["kpi"],
        channels=tuple(data["channels"]),
        date_start=data["date_start"],
        date_end=data["date_end"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train an MMM on a dataset and YAML config.")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--request", help="JSON-encoded MMMRequest; omit to use every configured channel")
    parser.add_argument("--chains", type=int)
    parser.add_argument("--tune", type=int)
    parser.add_argument("--draws", type=int)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")

    from integrations.training.mmm.trainer import MMMTrainer

    try:
        trainer = MMMTrainer(
            data_path=args.data,
            config_path=args.config,
            output_dir=args.output_dir,
            request=_request(args.request),
            progress=_progress,
            chains=args.chains,
            tune=args.tune,
            draws=args.draws,
        )
        result = trainer.run()
    except Exception as exc:
        emit(RESULT_PREFIX, {"status": "error", "message": f"{type(exc).__name__}: {exc}"})
        return 1
    emit(RESULT_PREFIX, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

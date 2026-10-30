from datetime import date
from typing import Any

from pydantic import Field, ValidationError

from agent.tools.base import ToolInput, ToolOutput
from agent.tools.system_ops.connectors.base import ConnectorTool
from integrations.training.mmm.channel_profile import ChannelProfile, ChannelStat, profile_spend
from integrations.training.mmm.dataset import check_sources, fetch_by_day
from integrations.training.mmm.plan import PlanError, SourceSpec, check_combine_groups
from integrations.training.scope import current_scope

DEFAULT_THRESHOLD_SHARE = 0.03


class CombineLowSpendChannelsInput(ToolInput):
    sources: list[SourceSpec] = Field(description="Connector tables and the metric outputs mapped from them, as in start_mmm_run.")
    kpi: str = Field(description="Output name of the KPI. Excluded from the spend profile.")
    controls: list[str] = Field(default_factory=list, description="Control outputs. Excluded from the spend profile.")
    date_start: date = Field(description="First date of the window to profile, YYYY-MM-DD.")
    date_end: date = Field(description="Last date of the window to profile, YYYY-MM-DD.")
    text_to_numeric: list[str] = Field(
        default_factory=list, description="Outputs whose source column is text holding numbers, as in preparation.text_to_numeric."
    )
    threshold_share: float = Field(
        default=DEFAULT_THRESHOLD_SHARE,
        ge=0,
        le=1,
        description="An output is low when its share of total candidate spend is below this. Default 0.03 (3%).",
    )
    combine_channels: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Proposed groups to validate and size, for example {'social_prospecting': ['meta_reach', 'meta_traffic']}. "
            "Empty means profile only. Build groups from the names and spend you see, not from fixed lists."
        ),
    )


def _format_stat(stat: ChannelStat) -> str:
    flag = " LOW" if stat.low else ""
    return (
        f"- {stat.name}: total {stat.total:,.0f} ({stat.share:.1%} of spend), "
        f"active {stat.active_days} days, mean {stat.mean_active:,.0f} on active days{flag}"
    )


def _proposal(groups: dict[str, list[str]], candidates: list[str]) -> dict[str, Any]:
    members = {member for group_members in groups.values() for member in group_members}
    channels = [name for name in candidates if name not in members] + list(groups)
    return {"preparation": {"combine_channels": groups}, "channels": channels}


class CombineLowSpendChannelsTool(ConnectorTool):
    name: str = "combine_low_spend_channels"
    description: str = (
        "Profile each candidate channel's spend over a window (total, share, active days, mean on active days) and flag "
        "low-spend ones. With combine_channels, validate proposed groups of related low-spend outputs and size them. "
        "Use it to decide whether channels should be combined before start_mmm_run. Read-only; saves nothing. "
        "The agent proposes the groups from names, spend and what the channels are; this tool only checks and measures them."
    )

    def get_input_schema(self) -> type[ToolInput]:
        return CombineLowSpendChannelsInput

    async def execute(self, **kwargs: Any) -> ToolOutput:
        blocked = self._blocked()
        if blocked is not None:
            return blocked
        org_id = current_scope().org_id
        try:
            args = CombineLowSpendChannelsInput(**kwargs)
            if args.date_start > args.date_end:
                raise PlanError("date_start must not be after date_end")
            outputs = [name for source in args.sources for name in source.metrics]
            for name in (args.kpi, *args.controls, *args.text_to_numeric):
                if name not in outputs:
                    raise PlanError(f"'{name}' is not a mapped output")
            check_combine_groups(args.combine_channels, outputs, args.kpi, args.controls)
            await check_sources(self.pool, self.datasets_schema, args.sources, args.text_to_numeric)
            by_day = await fetch_by_day(
                self.pool, self.datasets_schema, org_id, args.sources, args.text_to_numeric, args.date_start, args.date_end
            )
        except (ValidationError, PlanError) as exc:
            return ToolOutput(success=False, error=f"The spend profile cannot be built: {exc}. Fix the input and try again.")

        candidates = [name for name in outputs if name != args.kpi and name not in args.controls]
        if not candidates:
            return ToolOutput(success=False, error="No candidate channels remain after excluding the kpi and controls.")
        profile = profile_spend(
            by_day, candidates, args.combine_channels, args.date_start, args.date_end, args.threshold_share
        )

        threshold = f"{args.threshold_share:.0%}"
        lines = [
            f"Spend profile {args.date_start} to {args.date_end}: {len(candidates)} candidate outputs, "
            f"total spend {profile.total_spend:,.0f}. Low means under {threshold} of total spend.",
            "Outputs, lowest share first:",
            *[_format_stat(stat) for stat in profile.channels],
        ]
        metadata: dict[str, Any] = {"profile": profile.to_dict()}
        if args.combine_channels:
            grouped = {member for members in args.combine_channels.values() for member in members}
            lines += ["Proposed combined groups:", *[_format_stat(stat) for stat in profile.groups]]
            still_low = [stat.name for stat in profile.channels if stat.low and stat.name not in grouped]
            lines.append(
                "Still low and not in a group: " + (", ".join(still_low) if still_low else "none") + "."
            )
            proposal = _proposal(args.combine_channels, candidates)
            metadata["proposal"] = proposal
            lines.append(
                "The groups are valid. Pass proposal.preparation.combine_channels as preparation.combine_channels and "
                "proposal.channels as channels in preview_mmm_dataset or start_mmm_run. Nothing was saved."
            )
        else:
            lines.append(
                "Profile only. Decide whether low-spend outputs share a purpose or sit close together, propose groups, "
                "and call this tool again with combine_channels to validate them."
            )
        return ToolOutput(result="\n".join(lines), metadata=metadata)

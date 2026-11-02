import asyncio
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agent.runtime import approval_payload
from agent.slash_commands import expand_slash_command
from agent.tools.base import BaseTool
from agent.tools.ml_ops.ml.plans.list_plans import ListPlansTool
from agent.tools.ml_ops.ml.plans.run_plan import RunPlanTool
from agent.tools.ml_ops.ml.plans.save_plan import SavePlanTool
from agent.tools.registry import STATIC_TOOLS, interrupt_policy
from integrations.model_registry.registry import InvalidModelName, ModelNameTaken
from integrations.plans.markdown import InvalidPlan, parse_plan_markdown, render_plan_markdown
from integrations.plans.store import PlanNameTaken, content_to_spec
from integrations.training.mmm.plan import PlanError
from integrations.training.scope import JobScope, bind_scope  # noqa: F401
from tests.test_api import ORG_A, USER_1, USER_2, auth, client, member, mint, raw_db, settings  # noqa: F401

SPEC = {
    "kpi": "revenue",
    "channels": ["tv", "search"],
    "controls": ["price"],
    "sources": [
        {
            "table": "sales_daily",
            "date_column": "date",
            "metrics": {"revenue": "revenue", "tv": "tv_spend", "price": "avg_price"},
        },
        {"table": "google_ads", "date_column": "date", "metrics": {"search": "search_spend"}},
    ],
    "date_start": "2024-01-01",
    "date_end": "2024-12-31",
    "overrides": {},
}
PLAN_MD = """# Weekly Revenue
- KPI: revenue
- Channels: tv, search
- Controls: price
- Window: 2024-01-01 to 2024-12-31
- Sources:
  - Table: sales_daily
    - Date column: date
    - Metrics: revenue=revenue; tv=tv_spend; price=avg_price
  - Table: google_ads
    - Date column: date
    - Metrics: search=search_spend
- Preparation:
- Overrides:
"""


@pytest.fixture()
def second_member(raw_db):
    raw_db.memberships.insert_one({"user_id": USER_2, "org_id": ORG_A, "role": "analyst", "status": "active"})


def _create(client, token, name, visibility="private", content=None):
    return client.post(
        "/api/v1/plans",
        json={"name": name, "description": "d", "visibility": visibility, "content": content or PLAN_MD},
        headers=auth(token),
    )


def _fake_submit(monkeypatch, client, *, result="job-1", raises=None):
    calls = []

    async def submit(**kwargs):
        calls.append(kwargs)
        if raises is not None:
            raise raises
        return result

    monkeypatch.setattr(client.app.state.training, "submit_mmm_plan", submit)
    return calls


def test_owner_creates_and_sees_a_private_plan(client, member):
    token = mint(user=USER_1)
    created = _create(client, token, "Weekly Revenue")
    assert created.status_code == 201
    body = created.json()
    assert body["is_owner"] is True and body["visibility"] == "private"
    assert "rationale" not in body["spec"]
    listed = client.get("/api/v1/plans", headers=auth(token)).json()
    assert [p["id"] for p in listed] == [body["id"]]


def test_private_plans_are_hidden_from_other_users(client, member, second_member):
    created = _create(client, mint(user=USER_1), "Weekly Revenue").json()
    other = mint(user=USER_2)
    assert client.get("/api/v1/plans", headers=auth(other)).json() == []
    assert client.get(f"/api/v1/plans/{created['id']}", headers=auth(other)).status_code == 404


def test_org_plans_are_visible_to_the_org_with_the_creator(client, member, second_member):
    created = _create(client, mint(user=USER_1), "Shared Revenue", visibility="org").json()
    listed = client.get("/api/v1/plans", headers=auth(mint(user=USER_2))).json()
    assert [p["id"] for p in listed] == [created["id"]]
    assert listed[0]["is_owner"] is False
    assert listed[0]["owner_email"] == "dev@example.com"


def test_names_are_unique_per_user_case_insensitively(client, member):
    token = mint(user=USER_1)
    assert _create(client, token, "Weekly Revenue").status_code == 201
    clash = _create(client, token, "weekly revenue")
    assert clash.status_code == 409
    assert "already exists" in clash.json()["detail"]


def test_other_users_private_name_does_not_block_a_name(client, member, second_member):
    assert _create(client, mint(user=USER_1), "Weekly Revenue").status_code == 201
    assert _create(client, mint(user=USER_2), "Weekly Revenue").status_code == 201


def test_org_plan_name_blocks_the_same_name_for_other_users(client, member, second_member):
    assert _create(client, mint(user=USER_1), "Shared Revenue", visibility="org").status_code == 201
    assert _create(client, mint(user=USER_2), "shared revenue").status_code == 409


def test_non_owner_cannot_edit_or_delete_a_shared_plan(client, member, second_member):
    created = _create(client, mint(user=USER_1), "Shared Revenue", visibility="org").json()
    other = auth(mint(user=USER_2))
    url = f"/api/v1/plans/{created['id']}"
    assert client.patch(url, json={"name": "Hijacked"}, headers=other).status_code == 404
    assert client.delete(url, headers=other).status_code == 404
    assert client.get(url, headers=other).json()["name"] == "Shared Revenue"


def test_owner_can_rename_and_delete(client, member):
    token = auth(mint(user=USER_1))
    created = _create(client, mint(user=USER_1), "Weekly Revenue").json()
    url = f"/api/v1/plans/{created['id']}"
    renamed = client.patch(url, json={"name": "Quarterly Revenue"}, headers=token)
    assert renamed.status_code == 200 and renamed.json()["name"] == "Quarterly Revenue"
    assert client.delete(url, headers=token).status_code == 204
    assert client.get(url, headers=token).status_code == 404


def test_invalid_spec_visibility_and_name_are_rejected(client, member):
    token = mint(user=USER_1)
    assert _create(client, token, "Bad spec", content="- KPI: revenue\n").status_code == 422
    assert _create(client, token, "Bad visibility", visibility="public").status_code == 422
    assert _create(client, token, "").status_code == 422


def test_markdown_plan_round_trips_through_the_parser():
    raw = parse_plan_markdown(PLAN_MD)
    assert raw["kpi"] == "revenue" and raw["channels"] == ["tv", "search"]
    assert raw["date_start"] == "2024-01-01" and raw["date_end"] == "2024-12-31"
    assert raw["sources"][0]["metrics"] == {"revenue": "revenue", "tv": "tv_spend", "price": "avg_price"}
    canonical, spec = content_to_spec(PLAN_MD)
    assert spec["sources"][1]["table"] == "google_ads"
    assert render_plan_markdown(parse_plan_markdown(canonical)) == canonical


def test_markdown_plan_accepts_preparation_and_overrides():
    text = """- KPI: revenue
- Channels: tv, search
- Window: 2024-01-01 to 2024-12-31
- Sources:
  - Table: sales_daily
    - Date column: date
    - Metrics: revenue=revenue; tv=tv_spend; search=search_spend
    - Filters: region=US
- Preparation:
  - Lags: tv=0,7
  - Rolling means: search=7
  - Holiday country: none
- Overrides:
  - adstock_iterations: 300
  - use_seasonality: false
"""
    raw = parse_plan_markdown(text)
    assert raw["preparation"]["lags"] == {"tv": [0, 7]}
    assert raw["preparation"]["rolling_means"] == {"search": 7}
    assert raw["preparation"]["holiday_country"] is None
    assert raw["overrides"] == {"adstock_iterations": 300, "use_seasonality": False}
    assert raw["sources"][0]["filters"] == {"region": "US"}


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("not a bullet", "must be a bullet"),
        ("- Bogus: 1", "unknown field"),
        ("- KPI: revenue\n- Channels: tv\n- Window: 2024-01-01\n", "window must be"),
        (
            "- KPI: revenue\n- Window: 2024-01-01 to 2024-12-31\n- Sources:\n  - Table: t\n"
            "    - Date column: date\n    - Metrics: revenue=revenue",
            "the plan is missing: channels",
        ),
        ("- KPI: revenue\n- Channels: tv\n- Window: 2024-01-01 to 2024-12-31\n- Sources:\n", "at least one source"),
        (
            "- KPI: revenue\n- Channels: tv\n- Window: 2024-01-01 to 2024-12-31\n- Sources:\n"
            "  - Table: t\n    - Date column: date\n    - Metrics: revenue",
            "expected 'output=value' pairs",
        ),
    ],
)
def test_markdown_plan_reports_readable_errors(text, message):
    with pytest.raises(InvalidPlan, match=message):
        parse_plan_markdown(text)


def test_slash_plan_is_expanded_only_as_a_leading_command():
    assert expand_slash_command("look at /plan later") == "look at /plan later"
    assert expand_slash_command("/planning ahead") == "/planning ahead"
    directive = expand_slash_command("/plan")
    assert directive.startswith("The user invoked /plan") and "User message:" not in directive
    with_text = expand_slash_command("/PLANS  Q3 revenue")
    assert "list_plans" in with_text and with_text.endswith("User message: Q3 revenue")


def test_created_plan_returns_its_markdown_content(client, member):
    body = _create(client, mint(user=USER_1), "Weekly Revenue").json()
    assert "KPI: revenue" in body["content"]
    assert body["spec"]["kpi"] == "revenue"


def test_run_creates_a_new_model_from_the_saved_plan(client, member, monkeypatch):
    plan = _create(client, mint(user=USER_1), "Weekly Revenue").json()
    calls = _fake_submit(monkeypatch, client, result="job-42")
    res = client.post(
        f"/api/v1/plans/{plan['id']}/runs", json={"model_name": "Q3 Revenue"}, headers=auth(mint(user=USER_1))
    )
    assert res.status_code == 202
    assert res.json() == {"job_id": "job-42"}
    (call,) = calls
    assert call["model_name"] == "Q3 Revenue"
    assert call["source"] == "train"
    assert call["plan"].kpi == "revenue"
    assert "model_id" not in call
    assert call["user_id"] == USER_1 and call["org_id"] == ORG_A


def test_run_reports_a_taken_model_name_with_suggestions(client, member, monkeypatch):
    plan = _create(client, mint(user=USER_1), "Weekly Revenue").json()
    _fake_submit(monkeypatch, client, raises=ModelNameTaken("Q3 Revenue", ["Q3 Revenue-a1b2", "Q3 Revenue-c3d4"]))
    res = client.post(
        f"/api/v1/plans/{plan['id']}/runs", json={"model_name": "Q3 Revenue"}, headers=auth(mint(user=USER_1))
    )
    assert res.status_code == 409
    assert res.json()["detail"] == {
        "code": "name_taken",
        "name": "Q3 Revenue",
        "suggestions": ["Q3 Revenue-a1b2", "Q3 Revenue-c3d4"],
    }


def test_run_rejects_an_invalid_model_name(client, member, monkeypatch):
    plan = _create(client, mint(user=USER_1), "Weekly Revenue").json()
    _fake_submit(monkeypatch, client, raises=InvalidModelName("bad name"))
    res = client.post(
        f"/api/v1/plans/{plan['id']}/runs", json={"model_name": "bad/name"}, headers=auth(mint(user=USER_1))
    )
    assert res.status_code == 422


def test_run_maps_a_plan_error_to_400(client, member, monkeypatch):
    plan = _create(client, mint(user=USER_1), "Weekly Revenue").json()
    _fake_submit(monkeypatch, client, raises=PlanError("registry missing"))
    res = client.post(
        f"/api/v1/plans/{plan['id']}/runs", json={"model_name": "Q3 Revenue"}, headers=auth(mint(user=USER_1))
    )
    assert res.status_code == 400


def test_run_of_another_users_private_plan_is_not_found(client, member, second_member, monkeypatch):
    plan = _create(client, mint(user=USER_1), "Weekly Revenue").json()
    calls = _fake_submit(monkeypatch, client)
    res = client.post(
        f"/api/v1/plans/{plan['id']}/runs", json={"model_name": "Q3 Revenue"}, headers=auth(mint(user=USER_2))
    )
    assert res.status_code == 404
    assert calls == []


class FakePlans:
    """In-memory stand-in for PlanStore with the same visibility and uniqueness rules."""

    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.created = []

    def _visible(self, user_id):
        return [d for d in self.docs if d["owner_id"] == user_id or d["visibility"] == "org"]

    async def list_visible(self, *, org_id, user_id):
        return self._visible(user_id)

    async def get_visible(self, *, org_id, user_id, plan_id):
        return next((d for d in self._visible(user_id) if d["id"] == plan_id), None)

    async def ensure_name_free(self, *, org_id, user_id, name, exclude_id=None):
        if any(d["name"].lower() == name.lower() for d in self._visible(user_id)):
            raise PlanNameTaken(name)

    async def create(self, *, org_id, user_id, owner_email, name, description, visibility, content):
        _, spec = content_to_spec(content)
        doc = {
            "id": f"plan-{len(self.docs) + 1}",
            "name": name,
            "description": description,
            "visibility": visibility,
            "content": content,
            "spec": spec,
            "owner_id": user_id,
            "owner_email": owner_email,
        }
        self.docs.append(doc)
        self.created.append(doc)
        return doc


def plan_doc(**changes):
    doc = {
        "id": "plan-1",
        "name": "Weekly Revenue",
        "description": "",
        "visibility": "private",
        "content": PLAN_MD,
        "spec": SPEC,
        "owner_id": USER_1,
        "owner_email": "dev@example.com",
    }
    doc.update(changes)
    return doc


class FakeModels:
    def __init__(self, taken=()):
        self.taken = set(taken)

    async def name_taken(self, *, org_id, user_id, name, exclude_model_id=None):
        return name in self.taken

    async def suggest_names(self, *, org_id, user_id, base, count=3):
        return [f"{base}-{suffix}" for suffix in ("a1b2", "c3d4", "e5f6")[:count]]


class FakeService:
    def __init__(self, plans, taken=(), submit_error=None):
        self.models = FakeModels(taken)
        self.plans = plans
        self.submits = []
        self._submit_error = submit_error

    async def submit_mmm_plan(self, **kwargs):
        if self._submit_error is not None:
            raise self._submit_error
        self.submits.append(kwargs)
        return "job-7"


class ToolState(TypedDict):
    out: str


def _tool_graph(tool: BaseTool, args: dict):
    async def node(state: ToolState) -> dict:
        return {"out": await tool.ainvoke(args)}

    builder = StateGraph(ToolState)
    builder.add_node("tool", node)
    builder.add_edge(START, "tool")
    builder.add_edge("tool", END)
    return builder.compile(checkpointer=MemorySaver())


async def _turn(tool, args, service, decision=None):
    bind_scope(JobScope(service=service, org_id=ORG_A, user_id=USER_1, chat_id="chat-1", actor_email="dev@example.com", plans=service.plans))
    try:
        graph = _tool_graph(tool, args)
        config = {"configurable": {"thread_id": "thread-1"}}
        await graph.ainvoke({"out": ""}, config)
        snapshot = await graph.aget_state(config)
        if not snapshot.interrupts or decision is None:
            return snapshot.values["out"], snapshot.interrupts
        final = await graph.ainvoke(Command(resume={"decisions": [decision]}), config)
        return final["out"], snapshot.interrupts
    finally:
        bind_scope(None)


def turn(tool, args, service, decision=None):
    return asyncio.run(_turn(tool, args, service, decision))


def test_plan_tools_are_registered_and_gate_themselves():
    names = {t.name for t in STATIC_TOOLS}
    assert {"list_plans", "run_plan", "save_plan"} <= names
    gated = interrupt_policy(STATIC_TOOLS)
    assert not {"list_plans", "run_plan", "save_plan"} & set(gated)


def test_list_plans_shows_own_and_org_plans_only():
    plans = FakePlans(
        [
            plan_doc(id="mine", name="Mine"),
            plan_doc(id="org", name="Org", visibility="org", owner_id=USER_2, owner_email="other@example.com"),
            plan_doc(id="theirs", name="Theirs", owner_id=USER_2, owner_email="other@example.com"),
        ]
    )
    out, interrupts = turn(ListPlansTool(), {}, FakeService(plans))
    assert not interrupts
    assert "- Mine (id mine, private, owner you)" in out
    assert "- Org (id org, org, owner other@example.com)" in out
    assert "Theirs" not in out


def test_list_plans_tells_the_agent_not_to_ask_the_user_to_create_one():
    out, _ = turn(ListPlansTool(), {}, FakeService(FakePlans()))
    assert "no saved plans" in out
    assert "Do not ask them to create one" in out


def test_plan_tools_are_unavailable_without_a_scope():
    bind_scope(None)
    assert "unavailable" in asyncio.run(ListPlansTool().ainvoke({}))


def test_run_plan_card_shows_the_saved_configuration_and_creates_a_new_model():
    service = FakeService(FakePlans([plan_doc()]))
    out, interrupts = turn(RunPlanTool(), {"plan_id": "plan-1", "model_name": "Q3 Revenue"}, service)
    assert out == "" and len(interrupts) == 1
    action = approval_payload(interrupts[0])["actions"][0]
    assert action["name"] == "run_plan"
    assert action["allowed_decisions"] == ["approve", "reject"]
    assert action["args"]["model"] == "Q3 Revenue"
    assert action["args"]["plan"] == "Weekly Revenue"
    assert action["args"]["configuration"] == SPEC
    assert "always creates a new model" in action["description"]

    out, _ = turn(RunPlanTool(), {"plan_id": "plan-1", "model_name": "Q3 Revenue"}, service, {"type": "approve"})
    assert "queued as job job-7" in out
    (submit,) = service.submits
    assert submit["model_id"] is None
    assert submit["model_name"] == "Q3 Revenue"
    assert submit["source"] == "train"
    assert submit["plan"].kpi == "revenue"


def test_rejecting_a_run_starts_no_job_and_keeps_the_reason():
    service = FakeService(FakePlans([plan_doc()]))
    out, _ = turn(
        RunPlanTool(),
        {"plan_id": "plan-1", "model_name": "Q3 Revenue"},
        service,
        {"type": "reject", "message": "wrong quarter"},
    )
    assert "no run was started" in out and "wrong quarter" in out
    assert service.submits == []


def test_run_plan_asks_for_a_unique_name_when_the_model_name_is_taken():
    service = FakeService(FakePlans([plan_doc()]), taken={"Q3 Revenue"})
    out, interrupts = turn(RunPlanTool(), {"plan_id": "plan-1", "model_name": "Q3 Revenue"}, service)
    assert not interrupts
    assert "already exists" in out
    assert "Q3 Revenue-a1b2" in out and "Q3 Revenue-c3d4" in out
    assert service.submits == []


def test_run_plan_reports_an_unknown_or_invisible_plan_without_approval():
    service = FakeService(FakePlans([plan_doc(id="theirs", owner_id=USER_2, visibility="private")]))
    out, interrupts = turn(RunPlanTool(), {"plan_id": "theirs", "model_name": "Q3 Revenue"}, service)
    assert "No plan with id theirs" in out
    assert not interrupts


def test_run_plan_rejects_an_invalid_model_name_without_approval():
    service = FakeService(FakePlans([plan_doc()]))
    out, interrupts = turn(RunPlanTool(), {"plan_id": "plan-1", "model_name": ""}, service)
    assert "Ask the user for a valid model name" in out
    assert not interrupts


def test_run_plan_refuses_a_stored_plan_that_no_longer_validates():
    broken = plan_doc(spec={"kpi": "revenue"})
    service = FakeService(FakePlans([broken]))
    out, interrupts = turn(RunPlanTool(), {"plan_id": "plan-1", "model_name": "Q3 Revenue"}, service)
    assert "cannot be run" in out
    assert not interrupts


def test_run_plan_reports_a_name_clash_that_appears_after_approval():
    service = FakeService(FakePlans([plan_doc()]), submit_error=ModelNameTaken("Q3 Revenue", ["Q3 Revenue-a1b2"]))
    out, _ = turn(RunPlanTool(), {"plan_id": "plan-1", "model_name": "Q3 Revenue"}, service, {"type": "approve"})
    assert "was created meanwhile" in out
    assert "Q3 Revenue-a1b2" in out


def test_save_plan_card_shows_the_configuration_and_stores_after_approval():
    plans = FakePlans()
    service = FakeService(plans)
    args = {
        "name": "Weekly Revenue",
        "description": "Weekly revenue with TV and search",
        "visibility": "private",
        "kpi": "revenue",
        "channels": ["tv", "search"],
        "controls": ["price"],
        "sources": SPEC["sources"],
        "date_start": "2024-01-01",
        "date_end": "2024-12-31",
    }
    out, interrupts = turn(SavePlanTool(), args, service)
    assert out == "" and len(interrupts) == 1
    action = approval_payload(interrupts[0])["actions"][0]
    assert action["name"] == "save_plan"
    assert action["args"]["name"] == "Weekly Revenue"
    assert action["args"]["visibility"] == "private"
    assert action["args"]["configuration"]["kpi"] == "revenue"
    assert "rationale" not in action["args"]["configuration"]
    assert plans.created == []

    out, _ = turn(SavePlanTool(), args, service, {"type": "approve"})
    assert "Saved plan 'Weekly Revenue'" in out
    (doc,) = plans.created
    assert doc["owner_id"] == USER_1 and doc["visibility"] == "private"


def test_rejecting_a_save_stores_nothing():
    plans = FakePlans()
    args = {
        "name": "Weekly Revenue",
        "kpi": "revenue",
        "channels": ["tv", "search"],
        "controls": ["price"],
        "sources": SPEC["sources"],
        "date_start": "2024-01-01",
        "date_end": "2024-12-31",
    }
    out, _ = turn(SavePlanTool(), args, FakeService(plans), {"type": "reject", "message": "not now"})
    assert "nothing was saved" in out and "not now" in out
    assert plans.created == []


def test_save_plan_asks_for_another_name_when_one_is_taken_without_approval():
    plans = FakePlans([plan_doc()])
    args = {
        "name": "weekly revenue",
        "kpi": "revenue",
        "channels": ["tv", "search"],
        "controls": ["price"],
        "sources": SPEC["sources"],
        "date_start": "2024-01-01",
        "date_end": "2024-12-31",
    }
    out, interrupts = turn(SavePlanTool(), args, FakeService(plans))
    assert "already exists" in out and "different name" in out
    assert not interrupts
    assert plans.created == []


def test_save_plan_rejects_an_invalid_visibility_without_approval():
    args = {
        "name": "Weekly Revenue",
        "visibility": "public",
        "kpi": "revenue",
        "channels": ["tv", "search"],
        "controls": ["price"],
        "sources": SPEC["sources"],
        "date_start": "2024-01-01",
        "date_end": "2024-12-31",
    }
    out, interrupts = turn(SavePlanTool(), args, FakeService(FakePlans()))
    assert "visibility must be one of" in out
    assert not interrupts

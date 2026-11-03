import functools
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.factory import build_dana_agent
from agent.tools.ml_ops.ml.training.run_training_script import RunTrainingScriptTool
from agent.tools.registry import STATIC_TOOLS
from api.main import create_app
from integrations.training import service as training_service
from integrations.training.drafts import MAX_SCRIPT_CHARS, DraftError, apply_script_edit, draft_dir
from integrations.training.mmm.dataset import DatasetResult
from integrations.training.mmm.run_folder import RUN_FILES
from integrations.training.mmm.sandbox import SandboxOutcome
from integrations.training.scope import JobScope, bind_scope
from integrations.training.service import TrainingService
from tests.fakes import ScriptedModel
from tests.test_api import ORG_A, USER_1, USER_2, auth, make_settings, member, mint, raw_db, settings, static_secret  # noqa: F401
from tests.test_chat_stream import new_chat
from tests.test_hitl import event, kinds, resume, send
from tests.test_mmm_run import make_plan, tool_args
from tests.test_training import fake_trainer, make_client, wait_for

HEADERS = auth(mint())
SCRIPT = "x = 1\ny = 2\nx = 3\n"
CREATE_CALL_ID = "call-create-1"


def prepare(client, user_id=USER_1, chat_id="chat-1"):
    svc = client.app.state.training
    return client.portal.call(functools.partial(
        svc.prepare_mmm_draft, org_id=ORG_A, user_id=user_id, chat_id=chat_id,
        plan=make_plan(), model_name="Plan Model",
    ))


def edit(client, run_id, old_text, new_text, user_id=USER_1, chat_id="chat-1"):
    svc = client.app.state.training
    return client.portal.call(functools.partial(
        svc.edit_mmm_draft, org_id=ORG_A, user_id=user_id, chat_id=chat_id,
        run_id=run_id, old_text=old_text, new_text=new_text,
    ))


def submit(client, run_id, script_sha256, user_id=USER_1, chat_id="chat-1"):
    svc = client.app.state.training
    return client.portal.call(functools.partial(
        svc.submit_mmm_draft, org_id=ORG_A, user_id=user_id, chat_id=chat_id,
        run_id=run_id, script_sha256=script_sha256,
    ))


def read_run_file(client, job_id, name):
    svc = client.app.state.training
    return client.portal.call(functools.partial(
        svc.read_run_file, org_id=ORG_A, user_id=USER_1, job_id=job_id, name=name,
    ))


def patch_training(monkeypatch):
    async def fake_validate(pool, schema, plan):
        return None

    async def fake_build(pool, schema, org_id, plan):
        return DatasetResult(columns=["date", "revenue"], rows=[{"date": "2024-01-01", "revenue": 1.0}],
                             log={"rows_kept": 1})

    async def fake_run_script(command, run_dir, on_progress, env=None):
        (run_dir / "evaluation.json").write_text("{}", encoding="utf-8")
        (run_dir / "mmm_model.nc").write_bytes(b"fake-model")
        return SandboxOutcome(code=0, result={"status": "success", "metrics": {"divergences": 0}}, tail=[])

    async def fake_name_check(self, **kwargs):
        return "Plan Model"

    monkeypatch.setattr(training_service, "validate_sources", fake_validate)
    monkeypatch.setattr(training_service, "build_dataset", fake_build)
    monkeypatch.setattr(training_service, "run_script", fake_run_script)
    monkeypatch.setattr(TrainingService, "_check_new_model_name", fake_name_check)


@pytest.fixture()
def drafts(raw_db, member, tmp_path, monkeypatch):
    patch_training(monkeypatch)
    with make_client("ok", tmp_path) as client:
        client.app.state.training._connector_pool = object()
        yield client


@pytest.mark.parametrize("run_id", ["../../etc", "A" * 32, "a" * 31, "g" * 32, "", None])
def test_draft_dir_rejects_malformed_run_ids(tmp_path, run_id):
    with pytest.raises(DraftError, match="valid run_id"):
        draft_dir(tmp_path, ORG_A, USER_1, "chat-1", run_id)


def test_draft_dir_is_separate_per_user_and_chat(tmp_path):
    run_id = "a" * 32
    mine = draft_dir(tmp_path, ORG_A, USER_1, "chat-1", run_id)
    assert mine.is_relative_to(tmp_path / "drafts")
    assert draft_dir(tmp_path, ORG_A, USER_2, "chat-1", run_id) != mine
    assert draft_dir(tmp_path, ORG_A, USER_1, "chat-2", run_id) != mine


def test_unique_edit_applies_and_leaves_the_rest_untouched():
    assert apply_script_edit(SCRIPT, "y = 2", "y = 5") == "x = 1\ny = 5\nx = 3\n"


@pytest.mark.parametrize(
    "old, new, fragment",
    [
        ("", "z = 0", "must not be empty"),
        ("missing", "z = 0", "not found"),
        ("x = ", "z = ", "appears 2 times"),
        ("y = 2", "y = (", "invalid Python"),
        ("y = 2", "y = 2  # " + "#" * MAX_SCRIPT_CHARS, "over the"),
    ],
)
def test_edits_that_cannot_apply_are_rejected(old, new, fragment):
    with pytest.raises(DraftError, match=fragment):
        apply_script_edit(SCRIPT, old, new)


def test_another_user_or_chat_cannot_edit_or_submit_a_draft(drafts):
    draft = prepare(drafts)
    with pytest.raises(LookupError):
        edit(drafts, draft.run_id, "y = 2", "y = 5", user_id=USER_2)
    with pytest.raises(LookupError):
        submit(drafts, draft.run_id, draft.script_sha256, user_id=USER_2)
    with pytest.raises(LookupError):
        edit(drafts, draft.run_id, "y = 2", "y = 5", chat_id="chat-2")


def test_submit_is_refused_when_the_script_differs_from_the_reviewed_sha(drafts, raw_db):
    draft = prepare(drafts)
    with pytest.raises(DraftError, match="changed after it was reviewed"):
        submit(drafts, draft.run_id, "0" * 64)
    assert raw_db.training_drafts.find_one({"run_id": draft.run_id})["status"] == "ready"
    assert raw_db.jobs.count_documents({}) == 0


def test_edited_script_is_what_runs_and_a_draft_runs_only_once(drafts, raw_db):
    draft = prepare(drafts)
    anchor = next(line for line in draft.script.splitlines() if line.strip() and draft.script.count(line) == 1)
    new_sha = edit(drafts, draft.run_id, anchor, anchor + "  # reviewed by user")
    assert new_sha != draft.script_sha256
    with pytest.raises(DraftError, match="changed after it was reviewed"):
        submit(drafts, draft.run_id, draft.script_sha256)

    job_id = submit(drafts, draft.run_id, new_sha)
    body = wait_for(drafts, job_id)
    assert body["status"] == "succeeded", body
    assert sorted(raw_db.jobs.find_one({"id": job_id})["artifact"]["stored"]) == sorted(RUN_FILES)
    assert b"# reviewed by user" in read_run_file(drafts, job_id, "train.py")

    with pytest.raises(DraftError, match="already"):
        submit(drafts, draft.run_id, new_sha)


def test_failed_run_records_no_model_version(drafts, raw_db, monkeypatch):
    async def failing(command, run_dir, on_progress, env=None):
        return SandboxOutcome(code=1, result={"status": "error", "message": "boom"}, tail=["boom"])

    monkeypatch.setattr(training_service, "run_script", failing)
    draft = prepare(drafts)
    job_id = submit(drafts, draft.run_id, draft.script_sha256)
    assert wait_for(drafts, job_id)["status"] == "failed"
    assert raw_db.jobs.find_one({"id": job_id})["model_version"] is None


def test_approval_text_shows_the_script_and_warns_when_it_no_longer_matches(drafts):
    draft = prepare(drafts)
    svc = drafts.app.state.training
    tool = RunTrainingScriptTool()
    bind_scope(JobScope(service=svc, org_id=ORG_A, user_id=USER_1, chat_id="chat-1"))
    try:
        text = tool.approval_text({"run_id": draft.run_id, "script_sha256": draft.script_sha256})
        assert "--- training script ---" in text
        assert draft.script_sha256 in text
        assert "Train Plan Model" in text
        assert "Warning" not in text

        anchor = next(line for line in draft.script.splitlines() if line.strip() and draft.script.count(line) == 1)
        edit(drafts, draft.run_id, anchor, anchor + "  # reviewed by user")
        stale = tool.approval_text({"run_id": draft.run_id, "script_sha256": draft.script_sha256})
        assert "Warning" in stale
    finally:
        bind_scope(None)


def test_registry_exposes_the_script_tools_and_not_the_retired_placeholders():
    names = {tool.name for tool in STATIC_TOOLS}
    assert {"create_training_script", "edit_training_script", "run_training_script"} <= names
    assert not names & {"initiate_ml_training", "create_ml_training_job"}


class DraftModel(ScriptedModel):
    """Calls create_training_script, then run_training_script with the run_id and sha the tool returned."""

    lookup: Any = None

    def _pick(self, messages) -> AIMessage:
        last = messages[-1]
        if isinstance(last, HumanMessage):
            return AIMessage(content="", tool_calls=[
                {"name": "create_training_script", "args": tool_args(), "id": CREATE_CALL_ID}
            ])
        if isinstance(last, ToolMessage) and last.tool_call_id == CREATE_CALL_ID:
            doc = self.lookup()
            assert doc is not None, f"create_training_script did not create a draft: {last.content}"
            return AIMessage(content="", tool_calls=[{
                "name": "run_training_script",
                "args": {"run_id": doc["run_id"], "script_sha256": doc["script_sha256"]},
                "id": "call-run-1",
            }])
        return AIMessage(content="Waiting for your decision.")

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.script = [self._pick(messages)]
        self.cursor = 0
        return super()._generate(messages, stop, run_manager, **kwargs)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self.script = [self._pick(messages)]
        self.cursor = 0
        yield from super()._stream(messages, stop, run_manager, **kwargs)


@pytest.fixture()
def agent_client(raw_db, member, tmp_path, monkeypatch):
    patch_training(monkeypatch)

    def factory(settings_, checkpointer):
        model = DraftModel(script=[], lookup=lambda: raw_db.training_drafts.find_one({}, {"_id": 0}))
        return build_dana_agent(model, settings_.agent_root, checkpointer=checkpointer)

    app = create_app(
        make_settings(training_output_dir=tmp_path),
        agent_factory=factory,
        jwt_secret_loader=static_secret,
        training_command_factory=fake_trainer("ok"),
    )
    with TestClient(app) as client:
        client.app.state.training._connector_pool = object()
        yield client


def test_run_approval_reaches_the_user_with_the_script_and_reviewed_sha(agent_client, raw_db):
    chat_id = new_chat(agent_client, HEADERS)
    events = send(agent_client, chat_id, content="Train a revenue model")
    assert "interrupt" in kinds(events), events
    action = event(events, "interrupt")["actions"][0]
    draft = raw_db.training_drafts.find_one({}, {"_id": 0})

    assert action["name"] == "run_training_script"
    assert action["allowed_decisions"] == ["approve", "reject"]
    assert action["args"]["script_sha256"] == draft["script_sha256"]
    assert "cannot be loaded" not in action["description"]
    assert "--- training script ---" in action["description"]
    assert draft["script_sha256"] in action["description"]


def test_rejecting_the_approval_leaves_the_draft_ready_and_starts_nothing(agent_client, raw_db):
    chat_id = new_chat(agent_client, HEADERS)
    send(agent_client, chat_id, content="Train a revenue model")
    resume(agent_client, chat_id, [{"type": "reject", "message": "Not yet"}])
    assert raw_db.training_drafts.find_one({}, {"_id": 0})["status"] == "ready"
    assert raw_db.jobs.count_documents({}) == 0

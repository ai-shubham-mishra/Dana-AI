from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from api.main import create_app
from tests.test_api import ORG_A, USER_2, auth, make_settings, member, mint, raw_db, settings, static_secret  # noqa: F401
from tests.test_chat_stream import REPLY, TODO_CALL, new_chat, parse_sse, scripted_factory
from tests.test_training import fake_trainer

HEADERS = auth(mint())
OTHER_HEADERS = auth(mint(user=USER_2))
START_ARGS = {"model": "mmm", "kpi": "sales", "channels": ["TV", "YouTube"], "date_range": "2024-01-01 to 2024-12-31"}
ASK_CALL = AIMessage(content="", tool_calls=[{"name": "ask_user", "args": {"question": "Which KPI?"}, "id": "call-ask-1"}])
START_CALL = AIMessage(content="", tool_calls=[{"name": "start_training_job", "args": START_ARGS, "id": "call-start-1"}])


def make_app(settings, script):
    return create_app(
        settings,
        agent_factory=scripted_factory(script),
        jwt_secret_loader=static_secret,
        training_command_factory=fake_trainer("ok"),
    )


@pytest.fixture()
def open_client(raw_db, member):
    with ExitStack() as stack:

        def _open(script):
            return stack.enter_context(TestClient(make_app(make_settings(), script)))

        yield _open


def send(client, chat_id, content="Plan the model", headers=HEADERS):
    res = client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": content}, headers=headers)
    assert res.status_code == 200, res.text
    return parse_sse(res.text)


def resume(client, chat_id, decisions, headers=HEADERS):
    return client.post(f"/api/v1/chats/{chat_id}/resume", json={"decisions": decisions}, headers=headers)


def event(events, name):
    return next(data for kind, data in events if kind == name)


def kinds(events):
    return [kind for kind, _ in events]


def tool_content(client, chat_id, call_id):
    values = client.app.state.agent.get_state({"configurable": {"thread_id": chat_id}}).values
    return next(m.content for m in values["messages"] if isinstance(m, ToolMessage) and m.tool_call_id == call_id)


def test_ask_user_pauses_the_run_without_done(open_client):
    client = open_client([ASK_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    events = send(client, chat_id)
    assert "interrupt" in kinds(events)
    assert "done" not in kinds(events)
    action = event(events, "interrupt")["actions"][0]
    assert action["name"] == "ask_user"
    assert action["allowed_decisions"] == ["respond"]
    assert action["args"]["question"] == "Which KPI?"


def test_pending_endpoint_matches_interrupt_and_clears_after_resume(open_client):
    client = open_client([ASK_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    interrupt = event(send(client, chat_id), "interrupt")
    pending = client.get(f"/api/v1/chats/{chat_id}/pending", headers=HEADERS).json()
    assert pending["interrupt_id"] == interrupt["interrupt_id"]
    assert resume(client, chat_id, [{"type": "respond", "message": "Revenue"}]).status_code == 200
    assert client.get(f"/api/v1/chats/{chat_id}/pending", headers=HEADERS).json() is None


def test_respond_feeds_the_reply_back_and_finishes(open_client):
    client = open_client([ASK_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    res = resume(client, chat_id, [{"type": "respond", "message": "Revenue"}])
    events = parse_sse(res.text)
    assert "error" not in kinds(events)
    assert "done" in kinds(events)
    assert tool_content(client, chat_id, "call-ask-1") == "Revenue"
    messages = client.get(f"/api/v1/chats/{chat_id}/messages", headers=HEADERS).json()
    assert any(m["role"] == "assistant" and "Hello there friend" in m["content"] for m in messages)


def test_approve_runs_the_gated_tool(open_client):
    client = open_client([START_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    action = event(send(client, chat_id), "interrupt")["actions"][0]
    assert action["name"] == "start_training_job"
    assert action["allowed_decisions"] == ["approve", "edit", "reject"]
    events = parse_sse(resume(client, chat_id, [{"type": "approve"}]).text)
    assert event(events, "tool_result")["name"] == "start_training_job"
    assert "done" in kinds(events)
    content = tool_content(client, chat_id, "call-start-1")
    assert "is queued on the bundled sample MMM dataset" in content
    job_id = content.split("Training job ")[1].split(" ")[0]
    assert client.get(f"/api/v1/jobs/{job_id}", headers=HEADERS).status_code == 200


def test_edit_changes_arguments_before_the_tool_runs(open_client):
    client = open_client([START_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    edited = {"name": "start_training_job", "args": {**START_ARGS, "kpi": "revenue"}}
    res = resume(client, chat_id, [{"type": "edit", "edited_action": edited}])
    assert res.status_code == 200
    content = tool_content(client, chat_id, "call-start-1")
    assert "invalid" in content
    assert "revenue" in content
    assert "is queued" not in content


def test_reject_returns_the_reason_to_the_model(open_client):
    client = open_client([START_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    res = resume(client, chat_id, [{"type": "reject", "message": "Wrong window"}])
    assert res.status_code == 200
    content = tool_content(client, chat_id, "call-start-1")
    assert "rejected" in content.lower()
    assert "Wrong window" in content
    assert "not connected" not in content


def test_invalid_decisions_are_rejected_and_run_stays_paused(open_client):
    client = open_client([START_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    assert resume(client, chat_id, [{"type": "respond", "message": "ok"}]).status_code == 422
    assert resume(client, chat_id, [{"type": "approve"}, {"type": "approve"}]).status_code == 422
    assert resume(client, chat_id, [{"type": "edit", "edited_action": {"name": "other", "args": {}}}]).status_code == 422
    assert resume(client, chat_id, [{"type": "edit"}]).status_code == 422
    assert client.get(f"/api/v1/chats/{chat_id}/pending", headers=HEADERS).json() is not None


def test_resume_without_pending_approval_is_conflict(open_client):
    client = open_client([REPLY])
    chat_id = new_chat(client, HEADERS)
    assert resume(client, chat_id, [{"type": "approve"}]).status_code == 409


def test_new_message_is_blocked_while_approval_is_pending(open_client):
    client = open_client([START_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    res = client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "Hurry"}, headers=HEADERS)
    assert res.status_code == 409


def test_other_user_cannot_see_or_resume_the_pending_approval(open_client, raw_db):
    raw_db.memberships.insert_one({"user_id": USER_2, "org_id": ORG_A, "role": "analyst", "status": "active"})
    client = open_client([START_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    assert client.get(f"/api/v1/chats/{chat_id}/pending", headers=OTHER_HEADERS).status_code == 404
    assert resume(client, chat_id, [{"type": "approve"}], headers=OTHER_HEADERS).status_code == 404


def test_pending_approval_survives_app_restart(raw_db, member):
    settings = make_settings()
    with TestClient(make_app(settings, [START_CALL, REPLY])) as first:
        chat_id = new_chat(first, HEADERS)
        pending_id = event(send(first, chat_id), "interrupt")["interrupt_id"]
    assert raw_db.agent_checkpoints.count_documents({}) > 0
    with TestClient(make_app(settings, [REPLY])) as second:
        pending = second.get(f"/api/v1/chats/{chat_id}/pending", headers=HEADERS).json()
        assert pending["interrupt_id"] == pending_id
        assert resume(second, chat_id, [{"type": "approve"}]).status_code == 200
        assert "is queued" in tool_content(second, chat_id, "call-start-1")


def ask_call(call_id, **args):
    return AIMessage(content="", tool_calls=[{"name": "ask_user", "args": {"question": "Pick", **args}, "id": call_id}])


SELECT_ARGS = {"response_type": "single_select", "options": ["meta_ads", "google_ads"]}
MULTI_ARGS = {"response_type": "multi_select", "options": ["TV", "YouTube", "Search"]}


def test_interrupt_carries_response_type_and_options(open_client):
    client = open_client([ask_call("call-typed-1", **SELECT_ARGS), REPLY])
    chat_id = new_chat(client, HEADERS)
    action = event(send(client, chat_id), "interrupt")["actions"][0]
    assert action["args"]["response_type"] == "single_select"
    assert action["args"]["options"] == ["meta_ads", "google_ads"]


def test_single_select_answer_reaches_the_agent_as_json(open_client):
    client = open_client([ask_call("call-typed-2", **SELECT_ARGS), REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    res = resume(client, chat_id, [{"type": "respond", "value": "google_ads"}])
    assert res.status_code == 200, res.text
    assert tool_content(client, chat_id, "call-typed-2") == '{"answer": "google_ads"}'


def test_multi_select_answer_reaches_the_agent_as_json(open_client):
    client = open_client([ask_call("call-typed-3", **MULTI_ARGS), REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    assert resume(client, chat_id, [{"type": "respond", "value": ["TV", "Search"]}]).status_code == 200
    assert tool_content(client, chat_id, "call-typed-3") == '{"answer": ["TV", "Search"]}'


@pytest.mark.parametrize(
    "args, value",
    [
        (SELECT_ARGS, "radio"),
        (SELECT_ARGS, ["meta_ads"]),
        (MULTI_ARGS, []),
        (MULTI_ARGS, ["TV", "TV"]),
        (MULTI_ARGS, ["TV", "Radio"]),
        ({"response_type": "number"}, "12"),
        ({"response_type": "number"}, True),
        ({"response_type": "boolean"}, "yes"),
        ({"response_type": "text"}, "   "),
    ],
)
def test_invalid_typed_answers_are_rejected_and_run_stays_paused(open_client, args, value):
    client = open_client([ask_call("call-typed-4", **args), REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    assert resume(client, chat_id, [{"type": "respond", "value": value}]).status_code == 422
    assert client.get(f"/api/v1/chats/{chat_id}/pending", headers=HEADERS).json() is not None


def test_typed_answer_without_options_falls_back_to_text(open_client):
    client = open_client([ask_call("call-typed-5", response_type="single_select"), REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    assert resume(client, chat_id, [{"type": "respond", "message": "Revenue"}]).status_code == 200
    assert tool_content(client, chat_id, "call-typed-5") == "Revenue"


def test_plan_survives_a_pause_and_settles_after_resume(open_client, raw_db):
    client = open_client([TODO_CALL, ASK_CALL, REPLY])
    chat_id = new_chat(client, HEADERS)
    send(client, chat_id)
    resume(client, chat_id, [{"type": "respond", "message": "Revenue"}])
    segments = list(
        raw_db.messages.find({"chat_id": chat_id, "role": "assistant", "todos": {"$ne": []}}).sort("created_at", 1)
    )
    assert [m["todos"] for m in segments] == [
        [{"content": "Collect KPI", "status": "in_progress"}],
        [{"content": "Collect KPI", "status": "completed"}],
    ]

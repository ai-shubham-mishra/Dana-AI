import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent.factory import build_dana_agent
from api.main import create_app
from integrations.keyvault.client import KeyVaultNotConfigured
from tests.fakes import ScriptedModel
from tests.test_api import ORG_A, ORG_B, USER_1, USER_2, auth, make_settings, member, mint, raw_db, settings, static_secret  # noqa: F401

TODO_CALL = AIMessage(
    content="",
    tool_calls=[
        {
            "name": "write_todos",
            "args": {"todos": [{"content": "Collect KPI", "status": "in_progress"}]},
            "id": "call-todo-1",
        }
    ],
)
REPLY = AIMessage(content="Hello there friend")


def scripted_factory(script):
    def factory(settings, checkpointer):
        return build_dana_agent(ScriptedModel(script=script), settings.agent_root, checkpointer=checkpointer)

    return factory


def failing_factory(settings, checkpointer):
    raise KeyVaultNotConfigured("missing AZURE_KEYVAULT_URL")


@pytest.fixture()
def chat_client(raw_db):
    settings = make_settings()
    with TestClient(create_app(settings, agent_factory=scripted_factory([TODO_CALL, REPLY]), jwt_secret_loader=static_secret)) as c:
        yield c


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def new_chat(client, headers) -> str:
    res = client.post("/api/v1/chats", headers=headers)
    assert res.status_code == 201
    return res.json()["id"]


def test_create_chat_returns_owned_chat(chat_client, member, raw_db):
    chat_id = new_chat(chat_client, auth(mint()))
    stored = raw_db.chats.find_one({"id": chat_id})
    assert stored["org_id"] == ORG_A and stored["user_id"] == USER_1
    assert stored["title"] == "New chat"


def test_send_message_streams_tokens_todos_and_tool_events(chat_client, member, raw_db):
    headers = auth(mint())
    chat_id = new_chat(chat_client, headers)
    res = chat_client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "Plan an MMM"}, headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(res.text)
    names = [name for name, _ in events]
    assert "tool_call" in names and "tool_result" in names
    assert names[-1] == "done"

    todos = [data["todos"] for name, data in events if name == "todos"]
    assert todos == [[{"content": "Collect KPI", "status": "in_progress"}]]

    text = "".join(data["text"] for name, data in events if name == "token")
    assert text.strip() == "Hello there friend"


def test_send_message_persists_both_turns_and_titles_chat(chat_client, member, raw_db):
    headers = auth(mint())
    chat_id = new_chat(chat_client, headers)
    chat_client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "Plan an MMM"}, headers=headers)

    msgs = chat_client.get(f"/api/v1/chats/{chat_id}/messages", headers=headers).json()
    assert [(m["role"], m["content"].strip()) for m in msgs] == [
        ("user", "Plan an MMM"),
        ("assistant", "Hello there friend"),
    ]
    listed = chat_client.get("/api/v1/chats", headers=headers).json()
    assert listed[0]["title"] == "Plan an MMM"


def test_other_user_cannot_read_or_post_to_chat(chat_client, member, raw_db):
    chat_id = new_chat(chat_client, auth(mint()))
    raw_db.memberships.insert_one({"user_id": USER_2, "org_id": ORG_A, "role": "analyst", "status": "active"})
    intruder = auth(mint(user=USER_2))
    assert chat_client.get(f"/api/v1/chats/{chat_id}/messages", headers=intruder).status_code == 404
    res = chat_client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "hi"}, headers=intruder)
    assert res.status_code == 404
    assert raw_db.messages.count_documents({"chat_id": chat_id}) == 0


def test_other_org_cannot_post_to_chat(chat_client, member, raw_db):
    chat_id = new_chat(chat_client, auth(mint()))
    res = chat_client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "hi"}, headers=auth(mint(org=ORG_B)))
    assert res.status_code == 403


def test_empty_message_is_rejected(chat_client, member):
    headers = auth(mint())
    chat_id = new_chat(chat_client, headers)
    res = chat_client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": ""}, headers=headers)
    assert res.status_code == 422


def test_split_reply_moves_text_before_boundary_into_thinking():
    from api.routes.chats import split_reply

    assert split_reply("\n Let me check.\n\n", 0) == ("", "Let me check.\n\n")
    assert split_reply("Checking files. Done.", 15) == ("Checking files.", "Done.")
    assert split_reply("Only process", 12) == ("Only process", "")


def test_key_vault_failure_returns_503_without_leaking_details(raw_db, member):
    with TestClient(create_app(make_settings(), agent_factory=failing_factory, jwt_secret_loader=static_secret)) as c:
        headers = auth(mint())
        chat_id = new_chat(c, headers)
        res = c.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "hi"}, headers=headers)
    assert res.status_code == 503
    assert "AZURE_KEYVAULT_URL" not in res.text
    assert raw_db.messages.count_documents({"chat_id": chat_id}) == 0


def test_agent_is_built_once_and_reused(raw_db, member):
    calls = []

    def counting_factory(settings, checkpointer):
        calls.append(1)
        return scripted_factory([REPLY])(settings, checkpointer)

    with TestClient(create_app(make_settings(), agent_factory=counting_factory, jwt_secret_loader=static_secret)) as c:
        headers = auth(mint())
        chat_id = new_chat(c, headers)
        c.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "one"}, headers=headers)
        c.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "two"}, headers=headers)
    assert len(calls) == 1

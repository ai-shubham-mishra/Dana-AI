import pytest

from agent.tools.system_ops.hitl.ask_user import check_answer, effective_type


def test_unknown_or_missing_type_is_text():
    assert effective_type({}) == "text"
    assert effective_type({"response_type": "single_select"}) == "text"
    assert effective_type({"response_type": "multi_select", "options": []}) == "text"
    assert effective_type({"response_type": "number"}) == "number"


def test_text_is_stripped_and_returned_as_is():
    assert check_answer({"response_type": "text"}, "  Revenue ") == "Revenue"


def test_number_and_boolean_answers_are_json():
    assert check_answer({"response_type": "number"}, 2.5) == '{"answer": 2.5}'
    assert check_answer({"response_type": "boolean"}, False) == '{"answer": false}'


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "3", None])
def test_number_rejects_non_finite_or_non_numeric(value):
    with pytest.raises(ValueError):
        check_answer({"response_type": "number"}, value)


def test_multi_select_keeps_user_order():
    args = {"response_type": "multi_select", "options": ["TV", "YouTube", "Search"]}
    assert check_answer(args, ["Search", "TV"]) == '{"answer": ["Search", "TV"]}'

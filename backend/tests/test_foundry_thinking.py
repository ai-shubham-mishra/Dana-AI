from integrations.llm.foundry import THINKING_BINDING_BETA, build_claude_model


class _Reader:
    def get_secret(self, name: str) -> str:
        return "https://foundry.example.test" if "ENDPOINT" in name else "test-key"


def test_sonnet_uses_adaptive_thinking_with_drop_block_binding():
    model = build_claude_model(_Reader(), "claude-sonnet-5-5")
    assert model.thinking == {
        "type": "adaptive",
        "display": "summarized",
        "block_binding": {"prefix_mismatch_behavior": "drop_block"},
    }
    assert model.betas == [THINKING_BINDING_BETA]


def test_haiku_keeps_thinking_disabled_without_binding_beta():
    model = build_claude_model(_Reader(), "claude-haiku-5-5")
    assert model.thinking == {"type": "disabled"}
    assert model.betas == []

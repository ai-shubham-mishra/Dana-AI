from langchain_anthropic import ChatAnthropic

from integrations.keyvault.client import KeyVaultReader

MAX_RESPONSE_TOKENS = 13000
MAX_INPUT_TOKENS = 200_000
ENDPOINT_SECRET = "AZURE-FOUNDARY-SC-API-ENDPOINT"
API_KEY_SECRET = "AZURE-FOUNDARY-SC-API-KEY"


def _thinking_off(model_name: str) -> dict:
    if "haiku" in model_name:
        return {"type": "disabled"}
    return {"type": "between_tools"}


def build_claude_model(reader: KeyVaultReader, model_name: str) -> ChatAnthropic:
    endpoint = reader.get_secret(ENDPOINT_SECRET).rstrip("/")
    return ChatAnthropic(
        model=model_name,
        anthropic_api_url=f"{endpoint}/anthropic",
        anthropic_api_key=reader.get_secret(API_KEY_SECRET),
        max_tokens=MAX_RESPONSE_TOKENS,
        thinking=_thinking_off(model_name),
        # Deepagents summarizes and truncates history only near 85% of this window, which keeps signed thinking blocks intact.
        profile={"max_input_tokens": MAX_INPUT_TOKENS},
    )

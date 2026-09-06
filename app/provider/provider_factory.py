import os
from collections.abc import Mapping

from app.provider.agent_provider import AgentProvider, DeterministicAgentProvider
from app.provider.openai_compatible_agent_provider import OpenAICompatibleAgentProvider


def build_agent_provider(environ: Mapping[str, str] | None = None) -> AgentProvider:
    env = os.environ if environ is None else environ
    provider_name = env.get("AGENT_PROVIDER", "deterministic")

    if provider_name == "deterministic":
        return DeterministicAgentProvider()

    if provider_name == "openai-compatible":
        api_key = env.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for openai-compatible provider.")
        return OpenAICompatibleAgentProvider(
            api_key=api_key,
            base_url=env.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout_seconds=float(env.get("OPENAI_TIMEOUT_SECONDS", "30")),
        )

    raise RuntimeError(f"Unsupported AGENT_PROVIDER: {provider_name}")

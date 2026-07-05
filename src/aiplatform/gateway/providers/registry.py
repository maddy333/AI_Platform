"""Provider registry: builds and stores live provider instances from config."""

from __future__ import annotations

import structlog

from aiplatform.gateway.config import GatewaySettings
from aiplatform.gateway.domain.errors import ModelNotFoundError
from aiplatform.gateway.domain.ports import LLMProvider

logger = structlog.stdlib.get_logger(__name__)


def build_registry(settings: GatewaySettings) -> "ProviderRegistry":
    """Construct a populated registry from gateway settings."""
    registry = ProviderRegistry()

    if settings.openai.enabled:
        from aiplatform.gateway.providers.openai import OpenAIProvider

        registry.register(OpenAIProvider(settings.openai))
        logger.info("provider_registered", provider="openai")

    if settings.anthropic.enabled:
        from aiplatform.gateway.providers.anthropic import AnthropicProvider

        registry.register(AnthropicProvider(settings.anthropic))
        logger.info("provider_registered", provider="anthropic")

    if settings.gemini.enabled:
        from aiplatform.gateway.providers.gemini import GeminiProvider

        registry.register(GeminiProvider(settings.gemini))
        logger.info("provider_registered", provider="gemini")

    if settings.azure_openai.enabled:
        from aiplatform.gateway.providers.azure_openai import AzureOpenAIProvider

        registry.register(AzureOpenAIProvider(settings.azure_openai))
        logger.info("provider_registered", provider="azure_openai")

    if settings.ollama.enabled:
        from aiplatform.gateway.providers.ollama import OllamaProvider

        registry.register(OllamaProvider(settings.ollama))
        logger.info("provider_registered", provider="ollama")

    if settings.vllm.enabled:
        from aiplatform.gateway.providers.vllm import VLLMProvider

        registry.register(VLLMProvider(settings.vllm))
        logger.info("provider_registered", provider="vllm")

    if settings.openrouter.enabled:
        from aiplatform.gateway.providers.openrouter import OpenRouterProvider

        registry.register(OpenRouterProvider(settings.openrouter))
        logger.info("provider_registered", provider="openrouter")

    logger.info("provider_registry_built", count=len(registry))
    return registry


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"Provider already registered: {provider.name}")
        self._providers[provider.name] = provider

    def get(self, name: str) -> LLMProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise ModelNotFoundError(
                f"Provider '{name}' is not configured",
                context={"provider": name},
            )

    def for_model(self, model: str) -> list[LLMProvider]:
        candidates = [
            p
            for p in self._providers.values()
            if p.supported_models is None or model in p.supported_models
        ]
        if not candidates:
            raise ModelNotFoundError(
                f"No provider is configured for model '{model}'",
                context={"model": model},
            )
        return candidates

    def all(self) -> list[LLMProvider]:
        return list(self._providers.values())

    def __len__(self) -> int:
        return len(self._providers)

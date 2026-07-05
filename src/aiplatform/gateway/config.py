"""Gateway provider configuration (nested under AIP_GATEWAY__ prefix).

Environment variable layout::

    AIP_GATEWAY__OPENAI__ENABLED=true
    AIP_GATEWAY__OPENAI__API_KEY=sk-...
    AIP_GATEWAY__ANTHROPIC__ENABLED=true
    AIP_GATEWAY__ANTHROPIC__API_KEY=sk-ant-...
    AIP_GATEWAY__GEMINI__ENABLED=true
    AIP_GATEWAY__GEMINI__API_KEY=...
    AIP_GATEWAY__AZURE_OPENAI__ENABLED=true
    AIP_GATEWAY__AZURE_OPENAI__API_KEY=...
    AIP_GATEWAY__AZURE_OPENAI__ENDPOINT=https://my-resource.openai.azure.com
    AIP_GATEWAY__OLLAMA__ENABLED=true
    AIP_GATEWAY__OLLAMA__BASE_URL=http://localhost:11434
    AIP_GATEWAY__VLLM__ENABLED=true
    AIP_GATEWAY__VLLM__BASE_URL=http://localhost:8001
    AIP_GATEWAY__OPENROUTER__ENABLED=true
    AIP_GATEWAY__OPENROUTER__API_KEY=sk-or-...
"""

from __future__ import annotations

from pydantic import BaseModel, Field, SecretStr


class CircuitBreakerSettings(BaseModel):
    failure_threshold: int = Field(default=5, ge=1)
    recovery_timeout: float = Field(default=30.0, ge=1.0)
    success_threshold: int = Field(default=2, ge=1)


class OpenAIProviderConfig(BaseModel):
    enabled: bool = False
    api_key: SecretStr | None = None
    base_url: str = "https://api.openai.com/v1"
    timeout: float = 120.0
    max_retries: int = 3
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)


class AnthropicProviderConfig(BaseModel):
    enabled: bool = False
    api_key: SecretStr | None = None
    base_url: str = "https://api.anthropic.com"
    timeout: float = 120.0
    max_retries: int = 3
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)


class GeminiProviderConfig(BaseModel):
    enabled: bool = False
    api_key: SecretStr | None = None
    timeout: float = 120.0
    max_retries: int = 3
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)


class AzureOpenAIProviderConfig(BaseModel):
    enabled: bool = False
    api_key: SecretStr | None = None
    endpoint: str = ""
    api_version: str = "2024-12-01-preview"
    timeout: float = 120.0
    max_retries: int = 3
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)


class OllamaProviderConfig(BaseModel):
    enabled: bool = False
    base_url: str = "http://localhost:11434"
    timeout: float = 300.0
    max_retries: int = 2
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)


class VLLMProviderConfig(BaseModel):
    enabled: bool = False
    base_url: str = "http://localhost:8001"
    api_key: SecretStr | None = None
    timeout: float = 120.0
    max_retries: int = 3
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)


class OpenRouterProviderConfig(BaseModel):
    enabled: bool = False
    api_key: SecretStr | None = None
    base_url: str = "https://openrouter.ai/api/v1"
    timeout: float = 120.0
    max_retries: int = 3
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)


class GatewaySettings(BaseModel):
    """Root gateway configuration block."""

    openai: OpenAIProviderConfig = Field(default_factory=OpenAIProviderConfig)
    anthropic: AnthropicProviderConfig = Field(default_factory=AnthropicProviderConfig)
    gemini: GeminiProviderConfig = Field(default_factory=GeminiProviderConfig)
    azure_openai: AzureOpenAIProviderConfig = Field(default_factory=AzureOpenAIProviderConfig)
    ollama: OllamaProviderConfig = Field(default_factory=OllamaProviderConfig)
    vllm: VLLMProviderConfig = Field(default_factory=VLLMProviderConfig)
    openrouter: OpenRouterProviderConfig = Field(default_factory=OpenRouterProviderConfig)
    rate_limit_rpm: int = Field(default=600, ge=1)

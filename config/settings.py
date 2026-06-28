"""Configuração central do harness.

Segredos (API keys) vêm só de variável de ambiente, nunca do código. Os nomes
estão em `.env.example`.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BIA_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Provider de LLM ---------------------------------------------------- #
    # "openai" cobre qualquer endpoint compativel (Groq, Gemini, Ollama,
    # OpenRouter); "anthropic" usa a SDK da Anthropic; "fake" e offline.
    llm_provider: str = "openai"

    # Anthropic (pago). A chave vem do ambiente; nunca logada, nunca commitada.
    anthropic_api_key: str | None = Field(default=None, repr=False)
    model: str = "claude-sonnet-4-6"
    judge_model: str = "claude-sonnet-4-6"

    # Provedor compativel com OpenAI. Default = Groq (gratis, sem cartao).
    # Para Ollama local: base_url http://localhost:11434/v1, model llama3.1,
    # api_key qualquer valor nao-vazio (o Ollama ignora). Para Gemini: base_url
    # https://generativelanguage.googleapis.com/v1beta/openai/.
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_base_url: str = "https://api.groq.com/openai/v1"
    openai_model: str = "llama-3.3-70b-versatile"

    max_tokens: int = 1024
    request_timeout_s: float = 30.0
    max_retries: int = 3
    temperature: float = 0.0  # 0 = respostas reproduziveis (valor central do projeto)

    # --- Reprodutibilidade -------------------------------------------------- #
    seed: int = 42

    # --- Harness ------------------------------------------------------------ #
    max_agent_steps: int = 6
    regenerate_on_orphan: bool = True  # tenta regenerar uma vez se houver número órfão

    # --- Verificador anti-alucinação --------------------------------------- #
    number_abs_tolerance: float = 0.01
    number_rel_tolerance: float = 0.005  # 0,5%
    allow_numbers_from_user: bool = True

    # --- Observabilidade ---------------------------------------------------- #
    log_level: str = "INFO"
    log_redact_pii: bool = True
    log_file: str | None = None  # se None, loga para stdout

    # --- Tabela de preços (USD por 1M tokens) para contabilidade de custo --- #
    price_input_per_mtok: float = 3.0
    price_output_per_mtok: float = 15.0

    def cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return round(
            input_tokens / 1_000_000 * self.price_input_per_mtok
            + output_tokens / 1_000_000 * self.price_output_per_mtok,
            6,
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Singleton de configuração (lazy)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

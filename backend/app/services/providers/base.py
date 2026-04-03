"""
base.py — Abstract base for all LLM provider adapters.
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class ProviderAdapter(ABC):

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name used in logs (e.g. 'ionos', 'anthropic')."""

    @abstractmethod
    def chat(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict]:
        """
        Execute a synchronous chat completion.
        Returns (text: str, usage: dict) where usage has input_tokens, output_tokens.
        """

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """Generate embeddings. Raises NotImplementedError if not supported."""
        raise NotImplementedError(f"{self.provider_name} does not support embeddings")

    def is_available(self) -> bool:
        """Return False if misconfigured (e.g. no API key)."""
        return True

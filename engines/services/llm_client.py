"""
LLM Client Service

Wrapper for Anthropic Claude API with retry logic and token tracking.
"""

import hashlib
import json
import logging
import os
from typing import Any

from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LLMClient:
    """Async client for Claude API with determinism tracking."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.0,  # Deterministic by default
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.temperature = temperature
        self._client: AsyncAnthropic | None = None

    @property
    def client(self) -> AsyncAnthropic:
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        response_format: str = "json",
    ) -> dict[str, Any]:
        """
        Generate a response from Claude.

        Args:
            prompt: User prompt
            system: System prompt
            max_tokens: Maximum tokens in response
            response_format: Expected format ("json" or "text")

        Returns:
            Dictionary with response and metadata for determinism envelope
        """
        messages = [{"role": "user", "content": prompt}]

        # Build request
        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
            "messages": messages,
        }

        if system:
            request_kwargs["system"] = system

        # Calculate prompt hash for reproducibility
        prompt_content = json.dumps(
            {"system": system, "messages": messages},
            sort_keys=True,
        )
        prompt_hash = hashlib.sha256(prompt_content.encode()).hexdigest()

        logger.info(f"Calling Claude API: model={self.model}, prompt_hash={prompt_hash[:16]}...")

        # Make API call
        response = await self.client.messages.create(**request_kwargs)

        # Extract response text
        raw_response = response.content[0].text
        response_hash = hashlib.sha256(raw_response.encode()).hexdigest()

        # Parse JSON if expected
        parsed_response = raw_response
        if response_format == "json":
            try:
                # Handle markdown code blocks
                if "```json" in raw_response:
                    json_str = raw_response.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_response:
                    json_str = raw_response.split("```")[1].split("```")[0].strip()
                else:
                    json_str = raw_response.strip()
                parsed_response = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                parsed_response = {"raw": raw_response, "parse_error": str(e)}

        return {
            "response": parsed_response,
            "raw_response": raw_response,
            "model_id": self.model,
            "prompt_hash": prompt_hash,
            "response_hash": response_hash,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "temperature": self.temperature,
        }

    async def classify(
        self,
        text: str,
        categories: list[dict],
        context: str | None = None,
    ) -> dict[str, Any]:
        """
        Classify text into one of the provided categories.

        Args:
            text: Text to classify
            categories: List of category dicts with 'code', 'title', 'description'
            context: Additional context for classification

        Returns:
            Classification result with confidence and reasoning
        """
        categories_text = "\n".join(
            f"- {c['code']}: {c['title']} - {c['description']}"
            for c in categories
        )

        system = """You are a classification expert. Analyze the input and classify it into exactly one of the provided categories.

Return your response as JSON with the following structure:
{
    "code": "the selected category code",
    "title": "the category title",
    "confidence": 0.0-1.0 confidence score,
    "reasoning": "brief explanation of why this category was selected",
    "alternatives": [{"code": "...", "confidence": 0.0-1.0}, ...]
}

Be precise and consistent. Use temperature 0 for deterministic results."""

        prompt = f"""Classify the following:

INPUT: {text}

{f"CONTEXT: {context}" if context else ""}

CATEGORIES:
{categories_text}

Return your classification as JSON."""

        return await self.generate(prompt, system=system, response_format="json")


# Singleton instance
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create singleton LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client

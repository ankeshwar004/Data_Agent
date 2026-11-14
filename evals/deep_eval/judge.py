from __future__ import annotations

import json
import os
import re

from deepeval.models import DeepEvalBaseLLM

import config


def _extract_json(text: str) -> str:
    """Pull a JSON object out of free-form model text (handles code fences)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def _text(response) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


class OpenRouterJudge(DeepEvalBaseLLM):
    """Judge LLM served via OpenRouter. Model comes from EVAL_JUDGE_MODEL."""

    def __init__(self, model_name: str | None = None):
        self.model_name = (
            model_name
            or os.getenv("EVAL_JUDGE_MODEL")
            or config.OPENROUTER_MODEL
        )
        super().__init__(self.model_name)

    def load_model(self):
        from langchain_openrouter import ChatOpenRouter

        return ChatOpenRouter(
            model=self.model_name,
            temperature=0,
            api_key=config.OPENROUTER_API_KEY,
        )

    def _parse(self, model, prompt: str, schema):
        # Prefer native structured output; fall back to JSON parsing because
        # some (free) models do not support it reliably.
        try:
            result = model.with_structured_output(schema).invoke(prompt)
            if result is not None:
                return result
        except Exception:
            pass
        raw = _text(model.invoke(prompt))
        return schema.model_validate(json.loads(_extract_json(raw)))

    async def _a_parse(self, model, prompt: str, schema):
        try:
            result = await model.with_structured_output(schema).ainvoke(prompt)
            if result is not None:
                return result
        except Exception:
            pass
        raw = _text(await model.ainvoke(prompt))
        return schema.model_validate(json.loads(_extract_json(raw)))

    def generate(self, prompt: str, schema=None):
        model = self.load_model()
        if schema is not None:
            return self._parse(model, prompt, schema)
        return _text(model.invoke(prompt))

    async def a_generate(self, prompt: str, schema=None):
        model = self.load_model()
        if schema is not None:
            return await self._a_parse(model, prompt, schema)
        return _text(await model.ainvoke(prompt))

    def get_model_name(self) -> str:
        return self.model_name

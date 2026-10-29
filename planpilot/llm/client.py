"""Single entry point for LLM calls: render prompt, call provider, parse, validate, retry."""

import json
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from string import Template

from pydantic import BaseModel

from planpilot.config import CACHE_DIR, PROMPT_DIR, PROVIDER_ORDER, PROVIDERS, offline_default
from planpilot.llm.cache import Cache, cache_key

MAX_ATTEMPTS = 3
MAX_ERROR_LINES = 10
MAX_RATE_LIMIT_WAIT = 30  # seconds; one bounded wait for a per-minute limit


class LLMError(Exception):
    pass


class OfflineError(LLMError):
    pass


class DailyQuotaExceeded(LLMError):
    pass


class TruncatedOutput(LLMError):
    pass


# (provider, prompt, temperature) -> response text
Transport = Callable[[str, str, float], str]


def render(prompt_name: str, variables: dict, prompt_dir: Path = PROMPT_DIR) -> str:
    text = (prompt_dir / f"{prompt_name}.md").read_text(encoding="utf-8")
    return Template(text).substitute(variables)


def extract_json(text: str) -> str:
    """Strip code fences and keep the outermost {...} block."""
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


class OpenAITransport:
    """Calls OpenAI-compatible endpoints with the `openai` SDK."""

    def __init__(self):
        self._clients: dict = {}
        self._json_mode: dict[str, bool] = {}

    def _client(self, provider: str):
        if provider not in self._clients:
            from openai import OpenAI

            cfg = PROVIDERS[provider]
            key = os.getenv(cfg["key_env"])
            if not key:
                raise LLMError(f"{cfg['key_env']} is not set")
            self._clients[provider] = OpenAI(
                api_key=key, base_url=cfg["base_url"], max_retries=0, timeout=120
            )
        return self._clients[provider]

    def __call__(self, provider: str, prompt: str, temperature: float) -> str:
        import openai

        kwargs = {
            "model": PROVIDERS[provider]["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_completion_tokens": 16000,
        }
        if self._json_mode.get(provider, True):
            kwargs["response_format"] = {"type": "json_object"}

        waited = False
        while True:
            try:
                r = self._client(provider).chat.completions.create(**kwargs)
                break
            except openai.BadRequestError as e:
                if "response_format" in kwargs and "response_format" in str(e).lower():
                    self._json_mode[provider] = False  # provider has no JSON mode: plain text
                    kwargs.pop("response_format")
                    continue
                raise LLMError(f"{provider}: {e}") from e
            except openai.RateLimitError as e:
                msg = str(e)
                if _is_daily_limit(msg):
                    raise DailyQuotaExceeded(f"{provider}: {msg}") from e
                if waited:
                    raise LLMError(f"{provider} rate limit: {msg}") from e
                waited = True
                time.sleep(_retry_after(msg))
            except openai.APIError as e:
                raise LLMError(f"{provider}: {e}") from e

        choice = r.choices[0]
        if choice.finish_reason == "length":
            raise TruncatedOutput("the response was cut off before the JSON was complete")
        return choice.message.content or ""


def _is_daily_limit(msg: str) -> bool:
    m = msg.lower()
    return "per day" in m or "(tpd)" in m or "(rpd)" in m or "perday" in m


def _retry_after(msg: str) -> float:
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", msg)
    seconds = (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else 10
    return min(seconds + 1, MAX_RATE_LIMIT_WAIT)


class LLMClient:
    def __init__(
        self,
        transport: Transport | None = None,
        cache_dir: Path = CACHE_DIR,
        offline: bool | None = None,
        prompt_dir: Path = PROMPT_DIR,
    ):
        self.offline = offline_default() if offline is None else offline
        self._transport = transport
        self.cache = Cache(cache_dir)
        self.prompt_dir = prompt_dir
        self.provider = PROVIDER_ORDER[0]

    @property
    def transport(self) -> Transport:
        if self._transport is None:
            self._transport = OpenAITransport()
        return self._transport

    def _call(self, prompt: str, temperature: float) -> str:
        """Call the active provider; move to the next one when its daily quota is used up."""
        while True:
            try:
                return self.transport(self.provider, prompt, temperature)
            except DailyQuotaExceeded:
                i = PROVIDER_ORDER.index(self.provider)
                if i + 1 >= len(PROVIDER_ORDER):
                    raise
                self.provider = PROVIDER_ORDER[i + 1]

    def _parse(
        self, text: str, schema_cls: type[BaseModel], check: Callable | None
    ) -> tuple[BaseModel | None, list[str]]:
        try:
            obj = schema_cls.model_validate(json.loads(extract_json(text)))
        except Exception as e:  # JSON or schema errors
            return None, [str(e)]
        if check is None:
            return obj, []
        try:
            return obj, list(check(obj))
        except Exception as e:  # e.g. the assembled Project fails validation
            return obj, [str(e)]

    def complete_json(
        self,
        prompt_name: str,
        variables: dict,
        schema_cls: type[BaseModel],
        use_cache: bool = True,
        temperature: float = 0.2,
        check: Callable[[BaseModel], list[str]] | None = None,
    ) -> BaseModel:
        """Return a validated `schema_cls`. `check` returns extra errors that trigger a retry."""
        if self.offline:
            raise OfflineError("offline mode: LLM calls are disabled")

        prompt = render(prompt_name, variables, self.prompt_dir)
        model = PROVIDERS[self.provider]["model"]
        key = cache_key(self.provider, model, prompt_name, prompt, schema_cls.__name__, temperature)
        if use_cache and (hit := self.cache.get(key)) is not None:
            obj, errors = self._parse(hit, schema_cls, check)
            if not errors:
                return obj

        current = prompt
        errors: list[str] = []
        for _ in range(MAX_ATTEMPTS):
            try:
                text = self._call(current, temperature)
            except TruncatedOutput as e:
                errors, text = [str(e)], None
            if text is not None:
                obj, errors = self._parse(text, schema_cls, check)
                if not errors:
                    if use_cache:
                        self.cache.put(key, text)
                    return obj
            feedback = "\n".join("\n".join(errors).splitlines()[:MAX_ERROR_LINES])
            current = prompt + "\n\n" + render("retry", {"errors": feedback}, self.prompt_dir)
        raise LLMError(f"no valid output after {MAX_ATTEMPTS} attempts: {errors[:3]}")

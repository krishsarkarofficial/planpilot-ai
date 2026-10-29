"""Hash-keyed dev cache for LLM responses. Dev speed and quota only, never the offline demo."""

import hashlib
import json
from pathlib import Path


def cache_key(
    provider: str, model: str, prompt_name: str, prompt: str, schema: str, temperature: float
) -> str:
    raw = json.dumps([provider, model, prompt_name, prompt, schema, temperature])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Cache:
    def __init__(self, directory: Path):
        self.directory = directory

    def get(self, key: str) -> str | None:
        path = self.directory / f"{key}.txt"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def put(self, key: str, text: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / f"{key}.txt").write_text(text, encoding="utf-8")

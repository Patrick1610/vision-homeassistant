"""Defense in depth redaction. AI bundles additionally exclude all source free text."""

import logging
import re

PATTERNS = [
    r"(?i)(?:bearer\s+)[A-Za-z0-9._~+/=-]+",
    r"\b(?:sk-|sk-ant-)[A-Za-z0-9_\-]{8,}",
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    r"(?i)(?:https?://|wss?://)\S+",
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    r"(?i)(?:password|secret|token|api[_ -]?key)\s*[:=]\s*[^\s,;]+",
]
SENSITIVE = re.compile(r"(?i)password|secret|token|credential|authorization|api.?key")


class Redactor:
    def __init__(self, secrets=()):
        self.secrets = sorted((s for s in secrets if s), key=len, reverse=True)

    def text(self, value: str, limit=4000) -> str:
        for secret in self.secrets:
            value = value.replace(secret, "[REDACTED]")
        for pattern in PATTERNS:
            value = re.sub(pattern, "[REDACTED]", value)
        return value[:limit] if limit is not None else value

    def clean(self, value, depth=0):
        if depth > 12:
            return "[DEPTH LIMIT]"
        if isinstance(value, dict):
            result = {}
            for index, (key, item) in enumerate(value.items()):
                safe_key = self.text(str(key))
                if safe_key != str(key):
                    safe_key = f"redacted_key_{index}"
                result[safe_key] = (
                    "[REDACTED]" if SENSITIVE.search(str(key)) else self.clean(item, depth + 1)
                )
            return result
        if isinstance(value, (list, tuple, set)):
            return [self.clean(v, depth + 1) for v in list(value)[:500]]
        if isinstance(value, bytes):
            return self.text(value.decode(errors="replace"))
        return self.text(value) if isinstance(value, str) else value


class RedactingFormatter(logging.Formatter):
    def __init__(self, original, redactor):
        super().__init__()
        self.original, self.redactor = original, redactor

    def format(self, record):
        return self.redactor.text(self.original.format(record), limit=None)


def protect_logging(redactor):
    if not logging.getLogger().handlers:
        logging.getLogger().addHandler(logging.StreamHandler())
    if logging.lastResort:
        logging.lastResort.setFormatter(RedactingFormatter(logging.Formatter(), redactor))
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx", "aiohttp"):
        for handler in logging.getLogger(name).handlers:
            original = handler.formatter or logging.Formatter()
            if isinstance(original, RedactingFormatter):
                original = original.original
            handler.setFormatter(RedactingFormatter(original, redactor))

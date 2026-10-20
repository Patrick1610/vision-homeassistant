"""Defense in depth redaction. AI bundles additionally exclude all source free text."""

import html
import logging
import re

PATTERNS = [
    r"(?i)(?:bearer\s+)[A-Za-z0-9._~+/=-]+",
    r"\b(?:sk-|sk-ant-)[A-Za-z0-9_\-]{8,}",
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
    r"(?i)(?:https?://|wss?://)\S+",
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    r"[\w.+-]{1,64}@[\w.-]{1,253}\.[A-Za-z]{2,63}",
    # Escaped nested JSON keys have ambiguous closing value quotes: discard the
    # remainder of that bounded line rather than retaining a partial secret.
    r"""(?i)\\+["'](?:password|secret|token|api[_ -]?key|authorization)\\+["']\s*[:=][^\r\n]*""",
    r"""(?i)["']?(?:password|secret|token|api[_ -]?key|authorization)["']?\s*[:=]\s*"""
    r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;}]+)""",
    r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b",
    r"(?i)(?:[A-Z]:\\|/(?:Users|home|config|data|mnt|media|share|ssl|root|var|tmp)/)\S+",
]
SENSITIVE = re.compile(r"(?i)password|secret|token|credential|authorization|api.?key")
MAX_REDACTION_INPUT = 16384
TRUNCATION_MARKER = "[TRUNCATED]"


class Redactor:
    def __init__(self, secrets=()):
        self.secrets = sorted((s for s in secrets if s), key=len, reverse=True)

    def text(self, value: str, limit=4000) -> str:
        for secret in self.secrets:
            value = value.replace(secret, "[REDACTED]")
        ceiling = MAX_REDACTION_INPUT if limit is None else min(limit, MAX_REDACTION_INPUT)
        value = self.bounded(value, ceiling)
        value = value.encode("utf-8", errors="replace").decode("utf-8")
        # Decode common textual escapes only after bounding all regex work.
        value = html.unescape(value).replace("\\/", "/")
        value = re.sub(
            r"\\u([a-fA-F0-9]{4})",
            lambda m: chr(int(m[1], 16)) if not 0xD800 <= int(m[1], 16) <= 0xDFFF else m[0],
            value,
        )
        for secret in self.secrets:
            value = value.replace(secret, "[REDACTED]")
        for pattern in PATTERNS:
            value = re.sub(pattern, "[REDACTED]", value)
        # Replacements can expand short secrets/URLs; preserve the final marker too.
        return self.bounded(value, ceiling)

    @staticmethod
    def bounded(value, ceiling):
        if len(value) > ceiling:
            room = max(0, ceiling - len(TRUNCATION_MARKER))
            boundary = value[room]
            value = value[:room]
            if not boundary.isspace() and value and not value[-1].isspace():
                pieces = value.rsplit(maxsplit=1)
                value = pieces[0] + " " if len(pieces) == 2 else ""
            value += TRUNCATION_MARKER
        return value

    def clean(self, value, depth=0):
        if depth > 12:
            return "[DEPTH LIMIT]"
        if isinstance(value, dict):
            result = {}
            for index, (key, item) in enumerate(value.items()):
                safe_key = self.text(str(key))
                sensitive = SENSITIVE.search(str(key)) or SENSITIVE.search(safe_key)
                if safe_key != str(key):
                    safe_key = f"redacted_key_{index}"
                result[safe_key] = "[REDACTED]" if sensitive else self.clean(item, depth + 1)
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

"""Closed public catalog and bounded plain-text source extraction; no transport."""

import hashlib
import json
import re
from html.parser import HTMLParser

from .ha import core_version as core_version

CATALOG = {
    "zha": {"upstream": "zigpy/zha"},
    "zwave_js": {"upstream": "zwave-js/node-zwave-js"},
    "esphome": {"upstream": "esphome/aioesphomeapi"},
    "mqtt": {"upstream": None},
}
# Closed public technical terms are not household identifiers, even when a local
# diagnostic projection separately aliases the same integration/service token.
PUBLIC_TERMS = frozenset(CATALOG) | {"configuration.yaml", "mqtt.publish"}


def public_text(value, aliases, limit):
    """Redact known private references only; never discover IDs in public prose."""
    text = aliases.redactor.text(str(value), limit)
    present = sorted(
        (key for key in aliases.identifiers if key not in PUBLIC_TERMS and key in text),
        key=lambda key: (-len(key), key),
    )
    if present:
        pattern = (
            r"(?<![A-Za-z0-9_.\[\-])(?:"
            + "|".join(map(re.escape, present))
            + r")(?![A-Za-z0-9_\]]|[.\-]+[A-Za-z0-9_])"
        )
        text = re.sub(pattern, lambda m: aliases.alias(m[0], aliases.identifiers[m[0]]), text)
    return aliases.redactor.text(text, limit)


DOCS = {
    "template_error": "/docs/configuration/templating/",
    "timeout": "/docs/scripts/",
    "automation": "/docs/scripts/",
    "optimization": "/docs/scripts/",
    "mode_conflict": "/docs/automation/modes/",
    "condition_stop": "/docs/scripts/conditions/",
    "missing_target": "/docs/scripts/perform-actions/",
    "availability": "/docs/configuration/troubleshooting/",
    "device_communication": "/docs/configuration/troubleshooting/",
    "incident": "/docs/configuration/troubleshooting/",
}
TERMS = {
    "availability": "unavailable",
    "device_communication": "device did not respond",
    "timeout": "timeout",
    "template_error": "template error",
    "missing_target": "missing target",
    "mode_conflict": "max runs",
    "condition_stop": "condition",
    "automation": "automation",
    "optimization": "delay",
    "incident": "unavailable",
}


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def allowed_request(url):
    """Revalidate server-owned URLs at dispatch; no generic allowed-host proxy."""
    import httpx

    parsed = httpx.URL(url)
    if (
        parsed.scheme != "https"
        or parsed.port not in {None, 443}
        or parsed.userinfo
        or parsed.fragment
    ):
        return False
    pairs = list(parsed.params.multi_items())
    query = dict(pairs)
    if len(query) != len(pairs):
        return False
    if parsed.host == "www.home-assistant.io":
        return not query and parsed.path in set(DOCS.values()) | {
            f"/integrations/{slug}/" for slug in CATALOG
        }
    if parsed.host != "api.github.com":
        return False
    repositories = {"home-assistant/core"} | {
        v["upstream"] for v in CATALOG.values() if v["upstream"]
    }
    if parsed.path == "/search/issues":
        return (
            set(query) == {"q", "per_page"}
            and query["per_page"] == "2"
            and query["q"]
            in {
                f"repo:{repo} is:issue {slug} {term}"
                for repo in repositories
                for slug in CATALOG
                for term in TERMS.values()
            }
        )
    manifest = re.fullmatch(
        r"/repos/home-assistant/core/contents/homeassistant/components/([a-z_]+)/manifest.json",
        parsed.path,
    )
    if manifest:
        return (
            manifest[1] in CATALOG
            and set(query) == {"ref"}
            and core_version(query["ref"]) is not None
        )
    issue = re.fullmatch(r"/repos/([^/]+/[^/]+)/issues/([1-9][0-9]{0,15})(/comments)?", parsed.path)
    if not issue or issue[1] not in repositories or int(issue[2]) > 9007199254740991:
        return False
    if not issue[3]:
        return not query
    return (
        set(query) == {"per_page", "page"}
        and query["per_page"] == "3"
        and bool(re.fullmatch(r"[1-9][0-9]{0,8}", query["page"]))
        and int(query["page"]) <= 333333334
    )


def source_hash(source):
    return digest(
        [{key: e[key] for key in ("excerpt_key", "heading", "text")} for e in source["excerpts"]]
    )


def project_sources(snapshot, scope):
    result, mapping = json.loads(canonical(snapshot)), {}
    for index, source in enumerate(result["sources"], 1):
        if source_hash(source) != source["content_sha256"]:
            raise ValueError("Public source content hash mismatch")
        for position, excerpt in enumerate(source["excerpts"], 1):
            ref = f"{scope}:S{index}:P{position}"
            excerpt["ref"] = ref
            mapping[ref] = {
                "source_key": source["source_key"],
                "source_digest": source["content_sha256"],
                "excerpt_key": excerpt["excerpt_key"],
            }
    return result, mapping


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = self.selected = self.hidden = 0
        self.stack, self.parts, self.sections = [], [], []
        self.heading, self.heading_parts, self.in_heading = "Overview", [], False
        self.title, self.in_title = [], False

    def handle_starttag(self, tag, attrs):
        if tag in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "keygen",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            return
        if len(self.stack) >= 128:
            raise ValueError("Public document nesting limit")
        selected = tag in {"main", "article"}
        hidden = tag in {
            "script",
            "style",
            "nav",
            "form",
            "header",
            "footer",
            "aside",
            "svg",
            "pre",
        }
        self.stack.append((tag, selected, hidden))
        self.selected += selected
        self.hidden += hidden
        if tag == "title":
            self.in_title = True
        if tag in {"h1", "h2", "h3", "h4"} and self.selected and not self.hidden:
            self.flush()
            self.in_heading, self.heading_parts = True, []
        if tag in {"p", "li", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in {"h1", "h2", "h3", "h4"} and self.in_heading:
            self.heading = " ".join(" ".join(self.heading_parts).split())[:200]
            self.in_heading = False
        if tag in {"p", "li", "div"}:
            self.parts.append(" ")
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                for _, selected, hidden in self.stack[index:]:
                    self.selected -= selected
                    self.hidden -= hidden
                del self.stack[index:]
                break

    def handle_data(self, text):
        if self.in_title:
            self.title.append(text[:200])
        if self.selected and not self.hidden:
            if self.in_heading:
                self.heading_parts.append(text)
            else:
                self.parts.append(text)

    def flush(self):
        text = " ".join(" ".join(self.parts).split())
        if text and len(self.sections) < 256:
            self.sections.append((self.heading, text[:6000]))
        self.parts = []


def plain(value):
    text = value if isinstance(value, str) else ""
    # Issue code/log blocks and embedded links/images are not retained as instructions.
    text = re.sub(r"```[\s\S]*?(?:```|$)", " [code/log omitted] ", text)
    text = re.sub(r"!\[[^\]\n]{0,500}\]\([^\)\n]{0,2000}\)", " [image omitted] ", text)
    text = re.sub(r"\[([^\]\n]{0,500})\]\([^\)\n]{0,2000}\)", r"\1", text)
    text = re.sub(r"<[^>]{0,2000}>", " ", text)
    text = re.sub(r"(?<!\w)@[A-Za-z0-9_-]{1,100}", "[public mention omitted]", text)
    return " ".join(text.split())


def document_excerpts(body, kind):
    parser = Document()
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.flush()
    words = set((TERMS[kind] + " troubleshoot unavailable troubleshooting").split())
    selected = sorted(
        enumerate(parser.sections),
        key=lambda entry: (-sum(word in entry[1][0].lower() for word in words), entry[0]),
    )[:2]
    return plain(" ".join(parser.title))[:200], [
        {"excerpt_key": f"p{index + 1}", "heading": heading, "text": plain(text)[:3000]}
        for index, (_, (heading, text)) in enumerate(sorted(selected))
        if len(plain(text)) >= 20
    ]

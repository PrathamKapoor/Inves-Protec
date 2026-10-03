"""Text cleaning, HTML stripping, unicode normalization, and link extraction.

Includes adversarial evasion countermeasures such as zero-width character stripping,
homoglyph/NFKC normalization, and control character cleanup.
"""
from __future__ import annotations

import html
import re
import unicodedata
from html.parser import HTMLParser


# Characters frequently injected to break pattern-matching (zero-width spaces, joiners, BOM)
ZERO_WIDTH_PATTERN = re.compile(
    r"[\u200B\u200C\u200D\u200E\u200F\uFEFF\u202A\u202B\u202C\u202D\u202E]"
)

# Standard URL pattern matching http and https
URL_PATTERN = re.compile(
    r"(?i)\bhttps?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"
)


class _HTMLTextExtractor(HTMLParser):
    """Safe streaming parser extracting plain text while discarding script/style blocks."""

    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self._pieces: list[str] = []
        self._ignore = False
        self._ignore_tags = {"script", "style", "noscript", "svg", "head"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._ignore_tags:
            self._ignore = True
        elif tag.lower() in {"p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"}:
            self._pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._ignore_tags:
            self._ignore = False
        elif tag.lower() in {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"}:
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignore:
            self._pieces.append(data)

    def get_text(self) -> str:
        return "".join(self._pieces)


def clean_text(text: str) -> str:
    """Clean and normalize investor-submitted content.

    1. Strips zero-width and bidirectional control characters.
    2. Decodes HTML entities and extracts text from HTML if present.
    3. Applies Unicode NFKC normalization (unifying fullwidth/halfwidth and ligatures).
    4. Normalizes whitespace and line breaks while preserving paragraph boundaries.
    """
    if not text:
        return ""

    # 1. Remove zero-width characters injected to evade keyword filters
    text = ZERO_WIDTH_PATTERN.sub("", text)

    # 2. Check if string contains HTML tags
    if "<" in text and ">" in text:
        parser = _HTMLTextExtractor()
        try:
            parser.feed(text)
            text = parser.get_text()
        except Exception:
            # Fallback regex tag stripper if parser fails on severely malformed markup
            text = re.sub(r"<[^>]+>", " ", text)

    # 3. Decode HTML entities (e.g. &amp;, &#8377; for ₹, etc.)
    text = html.unescape(text)

    # 4. Unicode NFKC normalization (converts homoglyphic variations to standard forms)
    text = unicodedata.normalize("NFKC", text)

    # 5. Remove non-printable control characters (keep \n, \r, \t)
    text = "".join(
        ch for ch in text if ch in "\n\r\t" or (not unicodedata.category(ch).startswith("C"))
    )

    # 6. Normalize newlines and collapse runaway whitespace
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    # Collapse more than two consecutive empty lines to a single blank line
    cleaned_lines: list[str] = []
    blank_count = 0
    for line in lines:
        if not line:
            blank_count += 1
            if blank_count <= 1:
                cleaned_lines.append("")
        else:
            blank_count = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def extract_urls(text: str) -> list[str]:
    """Extract unique HTTP and HTTPS URLs from text in order of appearance."""
    if not text:
        return []
    raw_matches = URL_PATTERN.findall(text)
    seen: set[str] = set()
    results: list[str] = []
    for match in raw_matches:
        # Strip trailing punctuation often caught by regex
        cleaned_url = match.rstrip(".,;:!?'\")>]} ")
        if cleaned_url and cleaned_url not in seen:
            seen.add(cleaned_url)
            results.append(cleaned_url)
    return results

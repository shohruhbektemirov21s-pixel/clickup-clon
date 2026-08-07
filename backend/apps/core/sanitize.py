"""Server-side HTML sanitisation (nh3 allow-list per docs/DATA_MODEL.md)."""

import nh3

ALLOWED_TAGS = {
    "p", "br", "strong", "em", "u", "s", "code", "pre", "a",
    "ul", "ol", "li", "h1", "h2", "h3", "blockquote", "hr",
}
ALLOWED_ATTRIBUTES = {"a": {"href", "target"}}


def clean_html(html: str) -> str:
    if not html:
        return ""
    # nh3 manages the rel attribute itself via link_rel (DATA_MODEL allow-list).
    return nh3.clean(
        html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, link_rel="noopener noreferrer"
    )


def strip_tags_text(html: str) -> str:
    return nh3.clean(html, tags=set())

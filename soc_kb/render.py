from __future__ import annotations

import html
import json
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def paragraph(value: Any) -> str:
    text = esc(value).replace("\n", "<br/>")
    return f"<p>{text}</p>"


def code(value: Any) -> str:
    return f"<pre><code>{esc(value)}</code></pre>"


def table(rows: list[tuple[str, Any]]) -> str:
    rendered = []
    for name, value in rows:
        if value in (None, "", [], {}):
            continue
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(item) for item in value)
        elif isinstance(value, dict):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        rendered.append(
            f"<tr><th>{esc(name)}</th><td>{esc(value)}</td></tr>"
        )
    return "<table><tbody>" + "".join(rendered) + "</tbody></table>"


def notice(title: str, text: str) -> str:
    return (
        '<div class="confluence-information-macro confluence-information-macro-warning">'
        f"<p><strong>{esc(title)}</strong></p>{paragraph(text)}</div>"
    )


def heading(text: str, level: int = 2) -> str:
    level = min(max(level, 1), 6)
    return f"<h{level}>{esc(text)}</h{level}>"

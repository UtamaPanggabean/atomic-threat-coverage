from __future__ import annotations

import argparse
import os
from collections import Counter
from pathlib import Path

from soc_kb.confluence import ConfluenceClient, publish
from soc_kb.sources import SECTION_ORDER, ValidationError, build_pages, plan_json


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Build and safely publish the Confluence-only ATC SOC knowledge base")
    result.add_argument("command", choices=("validate", "plan", "publish"))
    result.add_argument("--repo", type=Path, default=Path.cwd())
    result.add_argument("--section", action="append", choices=SECTION_ORDER, dest="sections")
    result.add_argument("--output", type=Path)
    result.add_argument("--apply", action="store_true", help="perform writes; publish is a dry-run without this flag")
    result.add_argument("--limit", type=int, default=100, help="maximum creates/updates per run")
    result.add_argument("--timeout", type=float, default=20)
    result.add_argument("--retries", type=int, default=4)
    return result


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValidationError(f"required environment variable is missing: {name}")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    pages = build_pages(args.repo.resolve(), args.sections or SECTION_ORDER)
    counts = Counter(page.section for page in pages)
    print("Validated page plan: " + ", ".join(f"{name}={counts[name]}" for name in SECTION_ORDER if counts[name]))
    print(f"Total pages: {len(pages)}")
    if args.command == "validate":
        return 0
    if args.command == "plan":
        value = plan_json(pages)
        if args.output:
            args.output.write_text(value + "\n", encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(value)
        return 0
    client = ConfluenceClient(
        _env("CONFLUENCE_BASE_URL"), _env("ATLASSIAN_EMAIL"), _env("ATLASSIAN_API_TOKEN"),
        timeout=args.timeout, retries=args.retries,
    )
    result = publish(
        client, pages, root_page_id=_env("CONFLUENCE_ROOT_PAGE_ID"),
        space_id=_env("CONFLUENCE_SPACE_ID"), apply=args.apply, limit=args.limit,
    )
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"{mode}: created={result.created}, updated={result.updated}, unchanged={result.unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

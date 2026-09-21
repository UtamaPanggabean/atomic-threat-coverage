#!/usr/bin/env python3
"""Compatibility entry point for the Confluence-only SOC KB tooling."""

from soc_kb.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

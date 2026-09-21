#!/bin/sh
set -eu

# Safe by default: the container validates local, pinned content only.
# A Confluence write requires the explicit command `publish --apply` plus
# scoped credentials and a root page ID.
exec python -m soc_kb.cli "$@"

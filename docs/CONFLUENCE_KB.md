# Confluence-only SOC knowledge base

This fork treats the ATC repositories as pinned content sources for a research knowledge base. It does not deploy to Elasticsearch, Kibana, TheHive, a SIEM, or any other external security system.

## Safe workflow

1. `git submodule update --init --recursive`
2. `python scripts/verify_pins.py`
3. `python -m soc_kb.cli validate`
4. `python -m soc_kb.cli plan --output confluence-plan.json`
5. Review the plan.
6. Run `python -m soc_kb.cli publish --limit 100` for an API-backed dry-run.
7. Add `--apply` only for an approved batch.

Publishing is scoped to the configured root page and resolves existing pages by exact title among the intended parent's direct children. The publisher does not search or update pages elsewhere in the space. Retries cover rate limiting and transient server errors. The default change limit is 100 pages per run.

Required environment variables for API publishing:

- `CONFLUENCE_BASE_URL`
- `CONFLUENCE_SPACE_ID`
- `CONFLUENCE_ROOT_PAGE_ID`
- `ATLASSIAN_EMAIL`
- `ATLASSIAN_API_TOKEN`

## Dependency order

The plan is always produced in this order:

1. Data Sources & Requirements
2. Detection Rules
3. Use Case Testing (Atomic Red Team)
4. Response
5. Mitigation

The Sigma adapter publishes vendor-neutral detection logic and intentionally does not invoke the obsolete `sigmac` tool or generate SIEM-specific queries.

Atomic Red Team pages are clearly marked as authorized lab-only content. They preserve prerequisites, commands, and cleanup guidance for controlled use-case validation, but the publisher never executes any procedure.

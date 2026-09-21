from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import yaml

from soc_kb.models import PageSpec
from soc_kb.render import code, esc, heading, notice, paragraph, table


ROOT_KEY = "root"
SECTION_ORDER = ("data", "detection", "triggers", "response", "mitigation")


class ValidationError(ValueError):
    pass


def _yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValidationError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected a YAML mapping")
    return value


def _git_yaml(repository: Path, relative: str) -> dict[str, Any]:
    """Read pinned content from Git, even if endpoint protection hides a test file."""
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"HEAD:{relative}"],
        check=False, capture_output=True,
    )
    if result.returncode:
        raise ValidationError(f"{repository / relative}: unable to read pinned Git object")
    try:
        value = yaml.safe_load(result.stdout.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ValidationError(f"{repository / relative}: invalid YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{repository / relative}: expected a YAML mapping")
    return value


def _required(path: Path, data: dict[str, Any], fields: Iterable[str]) -> None:
    missing = [field for field in fields if data.get(field) in (None, "", [])]
    if missing:
        raise ValidationError(f"{path}: missing required fields: {', '.join(missing)}")


def _category(key: str, title: str, parent: str, section: str, text: str) -> PageSpec:
    body = heading(title, 1) + paragraph(text)
    return PageSpec(key, title, parent, body, section, "generated")


def _source_link(path: Path, repository: str, revision: str, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    return f"{repository}/blob/{revision}/{relative}"


def build_data_pages(repo: Path, revision: str) -> list[PageSpec]:
    base = repo / "data" / "atc_data"
    pages = [
        _category("data", "Data Sources & Requirements", ROOT_KEY, "data", "Telemetry prerequisites for SOC detection and investigation."),
        # These three categories already exist directly beneath the established
        # Confluence root. Keeping that scope prevents a duplicate migration.
        _category("data/logging", "Logging Policies", ROOT_KEY, "data", "Logging policy requirements."),
        _category("data/needed", "Data Needed", ROOT_KEY, "data", "Events and fields required by detection content."),
        _category("data/enrichments", "Enrichments", ROOT_KEY, "data", "Context that improves triage and investigation."),
    ]
    groups = (
        ("logging_policies", "data/logging", ("title",)),
        ("data_needed", "data/needed", ("title",)),
        ("enrichments", "data/enrichments", ("title",)),
    )
    for directory, parent, required in groups:
        for path in sorted((base / directory).glob("*.yml")):
            item = _yaml(path)
            _required(path, item, required)
            title = str(item["title"])
            body = heading(title, 1) + table(
                [(key.replace("_", " ").title(), value) for key, value in item.items() if key != "title"]
            )
            pages.append(PageSpec(f"{parent}/{path.stem}", title, parent, body, "data", str(path)))
    return pages


def build_detection_pages(repo: Path, revision: str) -> list[PageSpec]:
    sigma = repo / "detection_rules" / "sigma"
    pages = [_category(
        "detection", "Detection Rules", ROOT_KEY, "detection",
        "Vendor-neutral Sigma rule documentation. No SIEM query conversion or external-system deployment is performed.",
    )]
    for path in sorted((sigma / "rules").rglob("*.yml")):
        item = _yaml(path)
        _required(path, item, ("title", "id", "logsource", "detection"))
        rule_id = str(item["id"])
        title = f"SIGMA {rule_id} — {item['title']}"
        body = heading(str(item["title"]), 1)
        body += table([
            ("Sigma ID", rule_id), ("Status", item.get("status")),
            ("Level", item.get("level")), ("Author", item.get("author")),
            ("Date", item.get("date")), ("Modified", item.get("modified")),
            ("Tags", item.get("tags")), ("Log source", item.get("logsource")),
        ])
        body += heading("Description") + paragraph(item.get("description", ""))
        body += heading("Detection logic") + code(yaml.safe_dump(item["detection"], sort_keys=False, allow_unicode=True))
        if item.get("falsepositives"):
            body += heading("False positives") + paragraph("\n".join(map(str, item["falsepositives"])))
        body += paragraph(f"Pinned source: {_source_link(path, 'https://github.com/SigmaHQ/sigma', revision, sigma)}")
        pages.append(PageSpec(f"detection/{rule_id}", title[:250], "detection", body, "detection", str(path)))
    return pages


def build_trigger_pages(repo: Path, revision: str) -> list[PageSpec]:
    import subprocess

    atomic = repo / "triggers" / "atomic-red-team"
    pages = [_category(
        "triggers", "Use Case Testing (Atomic Red Team)", ROOT_KEY, "triggers",
        "Authorized lab-only detection validation procedures mapped to MITRE ATT&CK. Review scope, approvals, isolation, cleanup, and telemetry before execution.",
    )]
    listing = subprocess.run(
        ["git", "-C", str(atomic), "ls-tree", "-r", "--name-only", "HEAD", "atomics"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    technique_files = []
    for name in listing:
        parts = Path(name).parts
        if len(parts) == 3 and parts[0] == "atomics" and parts[2] == f"{parts[1]}.yaml":
            technique_files.append(name)
    for relative in sorted(technique_files):
        path = atomic / relative
        item = _git_yaml(atomic, relative)
        _required(path, item, ("attack_technique", "display_name", "atomic_tests"))
        technique = str(item["attack_technique"])
        body = heading(f"{technique}: {item['display_name']}", 1)
        body += notice(
            "Authorized lab use only",
            "These procedures can alter systems, download tools, create accounts, or change security controls. Never run them from Confluence. Execute only in an isolated, approved test environment with rollback and monitoring in place.",
        )
        for test in item.get("atomic_tests", []):
            if not isinstance(test, dict):
                continue
            body += heading(str(test.get("name", "Unnamed atomic test")), 2)
            executor = test.get("executor") if isinstance(test.get("executor"), dict) else {}
            body += table([
                ("Test ID", test.get("auto_generated_guid")),
                ("Platforms", test.get("supported_platforms")),
                ("Executor", executor.get("name")),
                ("Elevation required", executor.get("elevation_required", False)),
                ("Cleanup supplied", bool(executor.get("cleanup_command"))),
            ])
            body += paragraph(test.get("description", ""))
            if test.get("input_arguments"):
                body += heading("Inputs", 3) + code(yaml.safe_dump(test["input_arguments"], sort_keys=False, allow_unicode=True))
            if test.get("dependencies"):
                body += heading("Prerequisites", 3) + code(yaml.safe_dump(test["dependencies"], sort_keys=False, allow_unicode=True))
            if executor:
                body += heading("Lab procedure", 3) + code(executor.get("command") or executor.get("steps") or "No command supplied")
                if executor.get("cleanup_command"):
                    body += heading("Cleanup", 3) + code(executor["cleanup_command"])
        body += paragraph(f"Pinned source: {_source_link(path, 'https://github.com/redcanaryco/atomic-red-team', revision, atomic)}")
        pages.append(PageSpec(f"triggers/{technique}", f"Atomic Red Team {technique} — {item['display_name']}"[:250], "triggers", body, "triggers", str(path)))
    return pages


def _generic_pages(repo: Path, directory: Path, parent: str, section: str, revision: str, repository_url: str) -> list[PageSpec]:
    pages = []
    for path in sorted(directory.glob("*.yml")):
        item = _yaml(path)
        _required(path, item, ("title",))
        title = str(item["title"])
        identifier = str(item.get("id") or path.stem)
        body = heading(title, 1)
        description = item.get("description")
        if description:
            body += heading("Description") + paragraph(description)
        body += table([
            (key.replace("_", " ").title(), value)
            for key, value in item.items() if key not in {"title", "description", "workflow"}
        ])
        if item.get("workflow"):
            body += heading("Workflow") + paragraph(item["workflow"])
        source_root = directory.parent
        body += paragraph(f"Pinned source: {_source_link(path, repository_url, revision, source_root)}")
        pages.append(PageSpec(f"{parent}/{identifier}", title[:250], parent, body, section, str(path)))
    return pages


def build_response_pages(repo: Path, revision: str) -> list[PageSpec]:
    base = repo / "response" / "atc_react"
    pages = [_category("response", "Response", ROOT_KEY, "response", "SOC response stages, actions, and playbooks.")]
    groups = (
        ("stages", "Response Stages", "response_stages"),
        ("actions", "Response Actions", "response_actions"),
        ("playbooks", "Response Playbooks", "response_playbooks"),
    )
    for suffix, title, directory in groups:
        key = f"response/{suffix}"
        pages.append(_category(key, title, "response", "response", title))
        pages.extend(_generic_pages(repo, base / directory, key, "response", revision, "https://github.com/atc-project/atc-react"))
    return pages


def build_mitigation_pages(repo: Path, revision: str) -> list[PageSpec]:
    base = repo / "mitigation" / "atc-mitigation"
    pages = [_category("mitigation", "Mitigation", ROOT_KEY, "mitigation", "Preventive and hardening guidance for the SOC knowledge base.")]
    groups = (
        ("systems", "Mitigation Systems", "mitigation_systems"),
        ("policies", "Mitigation Policies", "mitigation_policies"),
        ("hardening", "Hardening Policies", "hardening_policies"),
    )
    for suffix, title, directory in groups:
        key = f"mitigation/{suffix}"
        pages.append(_category(key, title, "mitigation", "mitigation", title))
        pages.extend(_generic_pages(repo, base / directory, key, "mitigation", revision, "https://github.com/atc-project/atc-mitigation"))
    return pages


def build_pages(repo: Path, sections: Iterable[str] = SECTION_ORDER) -> list[PageSpec]:
    wanted = tuple(section for section in SECTION_ORDER if section in set(sections))
    unknown = set(sections) - set(SECTION_ORDER)
    if unknown:
        raise ValidationError(f"unknown sections: {', '.join(sorted(unknown))}")
    revisions = submodule_revisions(repo)
    builders = {
        "data": lambda: build_data_pages(repo, revisions["data/atc_data"]),
        "detection": lambda: build_detection_pages(repo, revisions["detection_rules/sigma"]),
        "triggers": lambda: build_trigger_pages(repo, revisions["triggers/atomic-red-team"]),
        "response": lambda: build_response_pages(repo, revisions["response/atc_react"]),
        "mitigation": lambda: build_mitigation_pages(repo, revisions["mitigation/atc-mitigation"]),
    }
    pages: list[PageSpec] = []
    for section in wanted:
        pages.extend(builders[section]())
    validate_plan(pages)
    return pages


def submodule_revisions(repo: Path) -> dict[str, str]:
    import subprocess

    paths = (
        "data/atc_data", "detection_rules/sigma", "triggers/atomic-red-team",
        "response/atc_react", "mitigation/atc-mitigation",
    )
    revisions = {}
    for relative in paths:
        result = subprocess.run(
            ["git", "-C", str(repo / relative), "rev-parse", "HEAD"],
            check=False, capture_output=True, text=True,
        )
        if result.returncode:
            raise ValidationError(f"submodule is not initialized: {relative}")
        revisions[relative] = result.stdout.strip()
    return revisions


def validate_plan(pages: list[PageSpec]) -> None:
    keys: set[str] = set()
    titles: set[tuple[str, str]] = set()
    for page in pages:
        if page.key in keys:
            raise ValidationError(f"duplicate page key: {page.key}")
        keys.add(page.key)
        title_scope = (page.parent_key, page.title.casefold())
        if title_scope in titles:
            raise ValidationError(f"duplicate title under {page.parent_key}: {page.title}")
        titles.add(title_scope)
        if page.parent_key != ROOT_KEY and page.parent_key not in keys:
            raise ValidationError(f"parent must precede child: {page.key} -> {page.parent_key}")
        if len(page.title) > 250:
            raise ValidationError(f"title exceeds 250 characters: {page.title}")


def plan_json(pages: list[PageSpec]) -> str:
    return json.dumps(
        [{"key": p.key, "title": p.title, "parent": p.parent_key, "section": p.section, "source": p.source} for p in pages],
        ensure_ascii=False, indent=2,
    )

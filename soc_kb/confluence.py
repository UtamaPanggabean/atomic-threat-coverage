from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from soc_kb.models import PageSpec
from soc_kb.sources import ROOT_KEY


class ConfluenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class PublishResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0


class ConfluenceClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        token: str,
        *,
        timeout: float = 20,
        retries: int = 4,
        session: requests.Session | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api = base_url.rstrip("/") + "/wiki/api/v2"
        self.timeout = timeout
        self.retries = retries
        self.session = session or requests.Session()
        self.session.auth = (email, token)
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        self.sleeper = sleeper

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        for attempt in range(self.retries + 1):
            try:
                response = self.session.request(method, self.api + path, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:
                if attempt == self.retries:
                    raise ConfluenceError(f"Confluence request failed: {exc}") from exc
                self.sleeper(min(2**attempt + random.random(), 30))
                continue
            if response.status_code not in {429, 500, 502, 503, 504}:
                if response.status_code >= 400:
                    raise ConfluenceError(f"Confluence {method} {path} returned {response.status_code}: {response.text[:500]}")
                return response
            if attempt == self.retries:
                raise ConfluenceError(f"Confluence {method} {path} failed after retries: {response.status_code}")
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt + random.random(), 30)
            self.sleeper(delay)
        raise AssertionError("unreachable")

    def children(self, parent_id: str) -> dict[str, dict[str, Any]]:
        pages: dict[str, dict[str, Any]] = {}
        path = f"/pages/{parent_id}/direct-children?limit=250"
        while path:
            payload = self.request("GET", path).json()
            for child in payload.get("results", []):
                if child.get("type") == "page":
                    pages[str(child["title"])] = child
            next_url = payload.get("_links", {}).get("next")
            if next_url and "/wiki/api/v2" in next_url:
                path = next_url.split("/wiki/api/v2", 1)[1]
            else:
                path = ""
        return pages

    def page(self, page_id: str) -> dict[str, Any]:
        return self.request("GET", f"/pages/{page_id}?body-format=storage").json()

    def create(self, space_id: str, parent_id: str, page: PageSpec) -> dict[str, Any]:
        payload = {
            "spaceId": space_id,
            "status": "current",
            "title": page.title,
            "parentId": parent_id,
            "body": {"representation": "storage", "value": page.body},
        }
        return self.request("POST", "/pages", json=payload).json()

    def update(self, page_id: str, current: dict[str, Any], page: PageSpec) -> dict[str, Any]:
        payload = {
            "id": page_id,
            "status": "current",
            "title": page.title,
            "body": {"representation": "storage", "value": page.body},
            "version": {"number": int(current["version"]["number"]) + 1, "message": "SOC KB scoped upsert"},
        }
        return self.request("PUT", f"/pages/{page_id}", json=payload).json()


def publish(
    client: ConfluenceClient,
    pages: list[PageSpec],
    *,
    root_page_id: str,
    space_id: str,
    apply: bool,
    limit: int,
) -> PublishResult:
    if limit < 1:
        raise ValueError("limit must be positive")
    ids = {ROOT_KEY: root_page_id}
    child_cache: dict[str, dict[str, dict[str, Any]]] = {}
    created = updated = unchanged = changes = 0
    for page in pages:
        parent_id = ids.get(page.parent_key)
        if not parent_id:
            raise ConfluenceError(f"parent was not resolved: {page.parent_key}")
        children = child_cache.setdefault(
            parent_id,
            {} if parent_id.startswith("dry-run:") else client.children(parent_id),
        )
        existing = children.get(page.title)
        if not existing:
            changes += 1
            if changes > limit:
                raise ConfluenceError(f"publish limit of {limit} changes exceeded")
            if apply:
                result = client.create(space_id, parent_id, page)
                page_id = str(result["id"])
                children[page.title] = result
            else:
                page_id = f"dry-run:{page.key}"
            ids[page.key] = page_id
            created += 1
            continue
        page_id = str(existing["id"])
        ids[page.key] = page_id
        current = client.page(page_id)
        current_body = current.get("body", {}).get("storage", {}).get("value", "")
        if current_body == page.body:
            unchanged += 1
            continue
        changes += 1
        if changes > limit:
            raise ConfluenceError(f"publish limit of {limit} changes exceeded")
        if apply:
            client.update(page_id, current, page)
        updated += 1
    return PublishResult(created, updated, unchanged)

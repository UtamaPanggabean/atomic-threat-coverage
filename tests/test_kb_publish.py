import pytest

from soc_kb.confluence import ConfluenceError, publish
from soc_kb.models import PageSpec


def spec(key, title, parent="root", body="<p>new</p>"):
    return PageSpec(key, title, parent, body, "data", "test")


class FakeClient:
    def __init__(self):
        self.tree = {"100": {"Existing": {"id": "101", "title": "Existing"}}}
        self.pages = {
            "101": {"id": "101", "title": "Existing", "version": {"number": 2}, "body": {"storage": {"value": "<p>old</p>"}}}
        }
        self.created = []
        self.updated = []

    def children(self, parent_id):
        return dict(self.tree.get(parent_id, {}))

    def page(self, page_id):
        return self.pages[page_id]

    def create(self, space_id, parent_id, page):
        result = {"id": str(200 + len(self.created)), "title": page.title}
        self.created.append((space_id, parent_id, page))
        return result

    def update(self, page_id, current, page):
        self.updated.append((page_id, current, page))
        return {"id": page_id}


def test_dry_run_never_writes_and_resolves_new_parent_locally():
    client = FakeClient()
    result = publish(
        client,
        [spec("category", "Category"), spec("child", "Child", "category")],
        root_page_id="100", space_id="space", apply=False, limit=2,
    )
    assert result.created == 2
    assert client.created == []
    assert client.updated == []


def test_apply_updates_only_exact_child_under_scoped_parent():
    client = FakeClient()
    result = publish(client, [spec("existing", "Existing")], root_page_id="100", space_id="space", apply=True, limit=1)
    assert result.updated == 1
    assert client.updated[0][0] == "101"


def test_publish_stops_at_change_limit():
    client = FakeClient()
    with pytest.raises(ConfluenceError, match="limit"):
        publish(
            client, [spec("a", "A"), spec("b", "B")],
            root_page_id="100", space_id="space", apply=True, limit=1,
        )
    assert len(client.created) == 1

from soc_kb.models import PageSpec
from soc_kb.sources import ValidationError, validate_plan


def page(key: str, title: str, parent: str = "root") -> PageSpec:
    return PageSpec(key, title, parent, "<p>body</p>", "data", "test")


def test_plan_requires_parent_before_child():
    try:
        validate_plan([page("child", "Child", "parent"), page("parent", "Parent")])
    except ValidationError as exc:
        assert "parent must precede child" in str(exc)
    else:
        raise AssertionError("invalid ordering was accepted")


def test_plan_rejects_duplicate_titles_in_same_parent():
    try:
        validate_plan([page("a", "Same"), page("b", "same")])
    except ValidationError as exc:
        assert "duplicate title" in str(exc)
    else:
        raise AssertionError("duplicate title was accepted")


def test_same_title_is_allowed_under_different_parents():
    validate_plan([
        page("parent-a", "A"),
        page("parent-b", "B"),
        page("child-a", "Shared", "parent-a"),
        page("child-b", "Shared", "parent-b"),
    ])

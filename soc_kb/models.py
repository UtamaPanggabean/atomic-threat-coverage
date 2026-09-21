from dataclasses import dataclass


@dataclass(frozen=True)
class PageSpec:
    key: str
    title: str
    parent_key: str
    body: str
    section: str
    source: str

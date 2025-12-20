from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FakeCategory:
    name: str


@dataclass
class FakeGroup:
    tg_chat_id: int
    title: str | None


class InMemoryBindingsRepository:
    def __init__(self) -> None:
        self.categories: dict[str, FakeCategory] = {}
        self.groups: dict[int, FakeGroup] = {}
        self.bindings: set[tuple[str, int]] = set()

    def create_category(self, name: str) -> None:
        if name in self.categories:
            raise ValueError("Category already exists")
        self.categories[name] = FakeCategory(name=name)

    def register_group(self, chat_id: int, title: str | None) -> None:
        self.groups[chat_id] = FakeGroup(tg_chat_id=chat_id, title=title)

    def bind_category(self, category_name: str, chat_id: int) -> None:
        if category_name not in self.categories:
            raise ValueError("Category not found")
        if chat_id not in self.groups:
            raise ValueError("Group not found")
        self.bindings.add((category_name, chat_id))

    def unbind_category(self, category_name: str, chat_id: int) -> None:
        self.bindings.discard((category_name, chat_id))

    def get_category_details(self, category_name: str):
        if category_name not in self.categories:
            raise ValueError("Category not found")
        links = []
        for cat, chat_id in self.bindings:
            if cat == category_name:
                group = self.groups[chat_id]
                links.append((cat, group))
        return self.categories[category_name], links


def test_bindings_create_delete_list() -> None:
    repo = InMemoryBindingsRepository()
    repo.create_category("jobs")
    repo.register_group(1001, "Group 1")

    repo.bind_category("jobs", 1001)
    _, links = repo.get_category_details("jobs")
    assert len(links) == 1

    repo.unbind_category("jobs", 1001)
    _, links = repo.get_category_details("jobs")
    assert links == []

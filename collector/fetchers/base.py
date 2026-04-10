from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict


class FetchedItem(TypedDict):
    external_id: str
    title: str
    url: str
    published_at: str | None
    summary: str | None
    raw_text: str | None


class BaseFetcher(ABC):
    def __init__(self, source: dict) -> None:
        self.source = source

    @abstractmethod
    def fetch(self) -> list[FetchedItem]: ...

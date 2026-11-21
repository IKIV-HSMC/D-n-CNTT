"""Validated generated mindmap payload used when a guest saves a result."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MindmapNodeSave(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=1600)
    parent_id: str | None = Field(default=None, max_length=80)


class MindmapGraphSave(BaseModel):
    nodes: list[MindmapNodeSave] = Field(min_length=1, max_length=10_000)


class FlashcardSave(BaseModel):
    front: str = Field(min_length=1, max_length=1000)
    back: str = Field(min_length=1, max_length=2000)
    node_id: str | None = Field(default=None, max_length=80)


class GeneratedMindmapSave(BaseModel):
    document_id: str | None = Field(default=None, max_length=80)
    mindmap: MindmapGraphSave
    flashcards: list[FlashcardSave] = Field(default_factory=list, max_length=10_000)
    mermaid: str | None = Field(default=None, max_length=2_000_000)
    backend: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=240)
    knowledge: dict[str, Any] | None = None
    reactflow: dict[str, Any] | None = None
    pipeline: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")

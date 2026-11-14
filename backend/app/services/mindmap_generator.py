from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.flashcard import Flashcard
from app.services.ai_pipeline import ProgressCallback, build_mermaid, generate_learning_material
from app.services.mindmap_engine import generate as engine_generate


async def generate_mindmap_result(
    *,
    mode: str,
    extracted_text: str,
    original_filename: str,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    title = Path(original_filename).stem
    if mode == "ai":
        result = await generate_learning_material(extracted_text, title, on_progress=on_progress)
    else:
        if on_progress is not None:
            await on_progress("engine", 45)
        result = engine_generate(
            {"extracted_text": extracted_text, "original_filename": original_filename},
            title=title,
        )
        result["backend"] = "structure_engine"
        result["model"] = "Bóc tách cấu trúc mục lục (Heading & Bullet points)"
        result["mermaid"] = build_mermaid(title, result["mindmap"].get("nodes", []))

    result["reactflow"] = _mindmap_to_reactflow(result.get("mindmap", {}))
    return result


async def persist_mindmap_result(
    db: AsyncSession,
    doc: Document,
    result: dict[str, Any],
) -> dict[str, Any]:
    result["flashcards"] = await _sync_flashcards(db, doc, result.get("flashcards", []))
    doc.mindmap_data = json.dumps(result, ensure_ascii=False)
    await db.flush()
    return result


async def _sync_flashcards(
    db: AsyncSession,
    doc: Document,
    generated_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Persist the latest deck while retaining review progress for unchanged cards."""
    existing_result = await db.execute(select(Flashcard).where(Flashcard.document_id == doc.id))
    existing_by_key = {card.card_key: card for card in existing_result.scalars().all()}
    for card in existing_by_key.values():
        card.is_active = False

    persisted: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for generated in generated_cards[:250]:
        front = " ".join(str(generated.get("front", "")).split()).strip()
        back = " ".join(str(generated.get("back", "")).split()).strip()
        if not front or not back:
            continue
        card_key = hashlib.sha256(f"{front.casefold()}\n{back.casefold()}".encode("utf-8")).hexdigest()
        if card_key in seen_keys:
            continue
        seen_keys.add(card_key)

        card = existing_by_key.get(card_key)
        if card is None:
            card = Flashcard(
                id=uuid.uuid5(uuid.NAMESPACE_URL, f"docmind:{doc.id}:{card_key}"),
                document_id=doc.id,
                card_key=card_key,
                front=front,
                back=back,
                node_id=generated.get("node_id"),
                is_active=True,
            )
            db.add(card)
        else:
            card.front = front
            card.back = back
            card.node_id = generated.get("node_id")
            card.is_active = True

        item = dict(generated)
        item.update({"id": str(card.id), "front": front, "back": back, "node_id": card.node_id})
        persisted.append(item)
    return persisted


def _mindmap_to_reactflow(mindmap: dict[str, Any], dx: int = 280, dy: int = 70) -> dict[str, Any]:
    nodes = mindmap.get("nodes", [])
    if not nodes:
        return {"nodes": [], "edges": []}

    children: dict[str | None, list[dict[str, Any]]] = {}
    for node in nodes:
        parent_id = node.get("parent_id")
        parent_id = None if parent_id in (None, "null", "") else str(parent_id)
        children.setdefault(parent_id, []).append(node)

    positions: dict[str, dict[str, int]] = {}
    row = 0

    def place(node: dict[str, Any], depth: int) -> float:
        nonlocal row
        node_id = str(node["id"])
        child_nodes = children.get(node_id, [])
        if child_nodes:
            child_y = [place(child, depth + 1) for child in child_nodes]
            y = sum(child_y) / len(child_y)
        else:
            y = row * dy
            row += 1
        positions[node_id] = {"x": depth * dx, "y": int(y)}
        return y

    for root in children.get(None, []):
        place(root, 0)
    for node in nodes:
        node_id = str(node["id"])
        if node_id not in positions:
            positions[node_id] = {"x": 0, "y": row * dy}
            row += 1

    return {
        "nodes": [
            {
                "id": str(node["id"]),
                "data": {"label": node.get("label", "")},
                "position": positions[str(node["id"])],
            }
            for node in nodes
        ],
        "edges": [
            {
                "id": f"e-{node['parent_id']}-{node['id']}",
                "source": str(node["parent_id"]),
                "target": str(node["id"]),
            }
            for node in nodes
            if node.get("parent_id") not in (None, "null", "")
        ],
    }

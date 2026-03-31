from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScanConfig:
    root: Path
    allowed_extensions: set[str]


def is_safe_relative_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    root_resolved = root.resolve()
    if root_resolved == candidate or root_resolved in candidate.parents:
        return candidate
    raise ValueError("Invalid path outside configured root")


def build_tree(config: ScanConfig) -> dict[str, Any]:
    root = config.root.resolve()
    return _scan_folder(root, root, config.allowed_extensions)


def _scan_folder(
    absolute_folder: Path, root: Path, allowed_extensions: set[str]
) -> dict[str, Any]:
    children: list[dict[str, Any]] = []

    for entry in sorted(absolute_folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if entry.is_dir():
            node = _scan_folder(entry, root, allowed_extensions)
            if node["children"]:
                children.append(node)
            continue

        if entry.is_file() and entry.suffix.lower() in allowed_extensions:
            rel_path = str(entry.relative_to(root))
            children.append(
                {
                    "name": entry.name,
                    "path": rel_path,
                    "type": "file",
                }
            )

    folder_rel = "." if absolute_folder == root else str(absolute_folder.relative_to(root))
    return {
        "name": absolute_folder.name,
        "path": folder_rel,
        "type": "folder",
        "children": children,
    }

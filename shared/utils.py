from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Node:
    type: str  # "file" | "dir"
    name: str
    rel_path: str
    children: Optional[List["Node"]] = None


def _iso8601(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _build_tree(root: Path, cur: Path) -> Node:
    """
    Build a directory tree rooted at `root`, currently visiting `cur`.
    All paths in output use POSIX-style separators in `rel_path`.
    """
    rel = cur.relative_to(root).as_posix()
    name = cur.name if rel != "." else cur.resolve().name  # root node name

    if cur.is_dir():
        children: List[Node] = []
        # sort for stable output: dirs first, then files, name asc
        entries = sorted(
            cur.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
        for p in entries:
            # skip broken symlinks safely
            try:
                children.append(_build_tree(root, p))
            except FileNotFoundError:
                continue

        return Node(
            type="dir",
            name=name,
            rel_path=rel,
            children=children,
        )

    # file or symlink to file
    return Node(
        type="file",
        name=name,
        rel_path=rel,
        children=None,
    )


def export_path_tree_to_json(path: str | Path) -> Dict[str, Any]:
    """
    Public API: given a path, return a structured JSON-serializable dict
    describing all files/dirs under it.
    """
    root = Path(path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    tree = _build_tree(root, root)

    payload: Dict[str, Any] = {
        "root": str(root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "tree": asdict(tree),
    }
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export directory contents into structured JSON."
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Directory path to scan recursively.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output JSON file path. If omitted, print to stdout.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent level.",
    )

    args = parser.parse_args(argv)

    payload = export_path_tree_to_json(args.path)
    text = json.dumps(payload, ensure_ascii=False, indent=args.indent)

    if args.out:
        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
DOC = ROOT / "docs" / "development" / "command-reference.md"
TARGET = re.compile(r"^([a-z][a-z0-9-]*):[^#]*##\s*(.+)$")


def catalogue() -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        if match := TARGET.match(line):
            result.append((match.group(1), match.group(2).strip()))
    return result


def list_commands() -> int:
    width = max(len(name) for name, _ in catalogue())
    for name, description in catalogue():
        print(f"{name:<{width}}  {description}")
    return 0


def check_commands() -> int:
    documented = DOC.read_text(encoding="utf-8")
    missing = [name for name, _ in catalogue() if f"`make {name}`" not in documented]
    if missing:
        raise SystemExit(f"Undocumented Make targets: {', '.join(missing)}")
    print(f"Validated {len(catalogue())} public Make targets.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("list", "check"), default="list", nargs="?")
    args = parser.parse_args()
    return check_commands() if args.action == "check" else list_commands()


if __name__ == "__main__":
    raise SystemExit(main())

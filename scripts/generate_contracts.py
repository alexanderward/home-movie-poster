from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic.json_schema import models_json_schema

from apps.server.apps.posters import contracts

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "apps" / "client" / "src" / "contracts.generated.ts"
MODELS = [
    contracts.DisplayState,
    contracts.MovieSummary,
    contracts.MovieDetail,
    contracts.MoviePage,
    contracts.MovieNightInput,
    contracts.MovieNightView,
    contracts.DiscoveredDeviceView,
    contracts.PlayerSettingsInput,
    contracts.ApplicationSettingsInput,
    contracts.ApplicationSettingsView,
    contracts.SessionView,
    contracts.HealthView,
    contracts.PosterSearchResult,
    contracts.PosterSearch,
    contracts.CollectionInput,
    contracts.CollectionSummary,
    contracts.CollectionList,
    contracts.CollectionDetail,
    contracts.ActiveCollectionInput,
    contracts.DisplayOverrideInput,
    contracts.DisplayOverrideView,
]


def type_for(schema: dict[str, Any]) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    if "anyOf" in schema:
        return " | ".join(dict.fromkeys(type_for(option) for option in schema["anyOf"]))
    kind = schema.get("type")
    if kind == "array":
        return f"Array<{type_for(schema.get('items', {}))}>"
    if kind in ("integer", "number"):
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "object":
        return "Record<string, unknown>"
    return "string" if kind == "string" else "unknown"


def generate() -> str:
    _, root = models_json_schema([(model, "validation") for model in MODELS])
    definitions = root["$defs"]
    lines = ["/* Generated from Pydantic contracts. Do not hand-edit. */", ""]
    for model in MODELS:
        schema = definitions[model.__name__]
        lines.append(f"export interface {model.__name__} {{")
        for name, field in schema.get("properties", {}).items():
            lines.append(f"  {name}: {type_for(field)};")
        lines.extend(["}", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    OUTPUT.write_text(generate(), encoding="utf-8", newline="\n")
    print(f"Generated {OUTPUT.relative_to(ROOT)}")

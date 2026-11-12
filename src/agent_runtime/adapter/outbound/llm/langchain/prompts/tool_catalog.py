import re
from typing import Any

from agent_runtime.domain.tool.tool_specification import ToolSpecification

NO_TOOLS: str = "(no tools are available right now)"
LONGEST_SUMMARY: int = 160
LONGEST_SHAPE: int = 240

_SENTENCE_END = re.compile(r"(?<=[.!?])\s")
_RETURNS = re.compile(r"\s*\bReturns:")
_JSON_TYPES: dict[str, str] = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "null": "None",
}


def tool_catalog(tools: list[ToolSpecification]) -> str:
    return "\n".join(_line(tool) for tool in tools) or NO_TOOLS


def planning_catalog(tools: list[ToolSpecification]) -> str:
    return "\n".join(_typed(tool) for tool in tools) or NO_TOOLS


def summary(description: str) -> str:
    described: str = _RETURNS.split(description, maxsplit=1)[0]
    first: str = _SENTENCE_END.split(described.strip(), maxsplit=1)[0].strip()
    first = " ".join(first.split())
    return _cut(first, LONGEST_SUMMARY)


def signature(tool: ToolSpecification) -> str:
    schema: dict[str, Any] = tool.parameters or {}
    definitions: dict[str, Any] = schema.get("$defs", {})
    required: set[str] = set(schema.get("required", ()))
    arguments: list[str] = []
    for name, field in (schema.get("properties") or {}).items():
        argument = f"{name}: {_render(field, definitions)}"
        if name not in required:
            argument += f" = {field.get('default')!r}"
        arguments.append(argument)
    returns: str = _shape(tool.output_schema)
    call: str = f"{tool.name}({', '.join(arguments)})"
    return f"{call} -> {returns}" if returns else call


def _line(tool: ToolSpecification) -> str:
    line: str = f"- {tool.name}: {summary(tool.description)}"
    arguments: list[str] = list(tool.parameters.get("properties") or {})
    return f"{line} Arguments: {', '.join(arguments)}." if arguments else line


def _typed(tool: ToolSpecification) -> str:
    about: str = summary(tool.description)
    return f"- {signature(tool)}\n  {about}" if about else f"- {signature(tool)}"


def _shape(schema: dict[str, Any] | None) -> str:
    if not schema:
        return ""
    return _cut(_render(schema, schema.get("$defs", {})), LONGEST_SHAPE)


def _render(node: dict[str, Any], definitions: dict[str, Any], depth: int = 0) -> str:
    if "$ref" in node:
        target: dict[str, Any] = definitions.get(node["$ref"].rsplit("/", 1)[-1], {})
        return _render(target, definitions, depth)
    if "const" in node:
        return repr(node["const"])
    if "enum" in node:
        return " | ".join(repr(value) for value in node["enum"])
    for key in ("anyOf", "oneOf"):
        if key in node:
            return " | ".join(_render(option, definitions, depth) for option in node[key])

    kind: Any = node.get("type")
    if isinstance(kind, list):
        return " | ".join(_render({**node, "type": one}, definitions, depth) for one in kind)
    if kind == "array":
        items: dict[str, Any] | None = node.get("items")
        return f"list[{_render(items, definitions, depth + 1)}]" if items else "list[Any]"
    if kind == "object" or "properties" in node:
        return _render_object(node, definitions, depth)
    return _JSON_TYPES.get(kind, "Any") if isinstance(kind, str) else "Any"


def _render_object(node: dict[str, Any], definitions: dict[str, Any], depth: int) -> str:
    properties: dict[str, Any] | None = node.get("properties")
    if properties and depth < 2:
        fields = (
            f"{name}: {_render(field, definitions, depth + 1)}"
            for name, field in properties.items()
        )
        return "{" + ", ".join(fields) + "}"
    if properties:
        return "{…}"
    values: Any = node.get("additionalProperties")
    if isinstance(values, dict) and values:
        return f"dict[str, {_render(values, definitions, depth + 1)}]"
    return "dict[str, Any]"


def _cut(text: str, longest: int) -> str:
    return text if len(text) <= longest else text[: longest - 1].rstrip() + "…"

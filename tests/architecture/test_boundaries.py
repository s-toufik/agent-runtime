import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "src"
PACKAGE = SOURCE / "agent_runtime"

FRAMEWORKS = {
    "fastapi",
    "litestar",
    "blacksheep",
    "starlette",
    "msgspec",
    "a2a",
    "google.protobuf",
    "sqlalchemy",
    "mcp",
    "langchain",
    "langchain_core",
    "langchain_openai",
    "langgraph",
    "pymongo",
    "pydantic",
    "httpx",
    "httpx2",
}


def _imports(directory: Path) -> dict[Path, set[str]]:
    found: dict[Path, set[str]] = {}
    for path in directory.rglob("*.py"):
        modules: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module)
        found[path] = modules
    return found


def _violations(directory: Path, forbidden: set[str]) -> list[str]:
    assert directory.is_dir(), f"{directory} does not exist"
    return [
        f"{path.relative_to(SOURCE)} imports {module}"
        for path, modules in _imports(directory).items()
        for module in modules
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in forbidden)
    ]


def test_the_domain_is_free_of_frameworks_and_outer_layers() -> None:
    forbidden = FRAMEWORKS | {
        "agent_runtime.application",
        "agent_runtime.adapter",
        "bootstrap",
    }
    assert _violations(PACKAGE / "domain", forbidden) == []


def test_the_application_depends_only_on_the_domain() -> None:
    forbidden = FRAMEWORKS | {"agent_runtime.adapter", "bootstrap"}
    assert _violations(PACKAGE / "application", forbidden) == []


def test_the_hexagon_never_imports_the_composition_root() -> None:
    assert _violations(PACKAGE, {"bootstrap"}) == []


def test_outbound_adapters_never_import_inbound_adapters() -> None:
    forbidden = {"agent_runtime.adapter.inbound"}
    assert _violations(PACKAGE / "adapter" / "outbound", forbidden) == []


INBOUND = PACKAGE / "adapter" / "inbound"
SHARED_INBOUND = {"exception"}


def test_inbound_adapters_never_import_each_other() -> None:
    adapters = {
        path.name
        for path in INBOUND.iterdir()
        if (path / "__init__.py").is_file() and path.name not in SHARED_INBOUND
    }
    violations = [
        violation
        for adapter in sorted(adapters)
        for violation in _violations(
            INBOUND / adapter,
            {f"agent_runtime.adapter.inbound.{other}" for other in adapters - {adapter}},
        )
    ]
    assert violations == []


def test_the_agent_never_imports_a_toolbox_package_directly() -> None:
    assert _violations(PACKAGE, {"toolbox", "agent_toolbox"}) == []


def test_langgraph_nodes_only_delegate_to_the_application() -> None:
    forbidden = {
        "agent_runtime.adapter.outbound.llm",
        "agent_runtime.adapter.outbound.tool",
        "langchain",
        "langchain_core",
        "langchain_openai",
    }
    assert _violations(PACKAGE / "adapter" / "outbound" / "langgraph", forbidden) == []


WEB_FRAMEWORKS = {"fastapi", "litestar", "blacksheep", "starlette", "sse_starlette", "msgspec"}
FASTAPI_APPLICATION = SOURCE / "bootstrap" / "application" / "fastapi"
A2A_ADAPTERS = (
    PACKAGE / "adapter" / "inbound" / "a2a",
    PACKAGE / "adapter" / "outbound" / "agent" / "a2a",
)


def test_the_agent_imports_no_web_framework() -> None:
    assert _violations(PACKAGE, WEB_FRAMEWORKS) == []


def test_only_the_fastapi_application_imports_a_web_framework_in_bootstrap() -> None:
    application = f"{FASTAPI_APPLICATION.relative_to(SOURCE)}/"
    outside = [
        violation
        for violation in _violations(SOURCE / "bootstrap", WEB_FRAMEWORKS)
        if not violation.startswith(application)
    ]
    assert outside == []


def test_the_fastapi_application_imports_no_other_web_framework() -> None:
    assert _violations(FASTAPI_APPLICATION, WEB_FRAMEWORKS - {"fastapi"}) == []


def test_only_the_a2a_adapters_import_the_a2a_sdk_in_the_agent() -> None:
    adapters = tuple(f"{adapter.relative_to(SOURCE)}/" for adapter in A2A_ADAPTERS)
    outside = [
        violation
        for violation in _violations(PACKAGE, {"a2a", "google.protobuf"})
        if not violation.startswith(adapters)
    ]
    assert outside == []


MCP_SDK = {"mcp", "pycraftcore.mcp_sdk"}
MCP_CLIENT_WIRING = SOURCE / "bootstrap" / "di" / "tools_di.py"


def test_the_agent_reaches_mcp_servers_only_through_pycraftcore_ports() -> None:
    assert _violations(PACKAGE, MCP_SDK) == []


def test_only_the_tools_wiring_builds_the_mcp_sdk_client_in_bootstrap() -> None:
    wiring = f"{MCP_CLIENT_WIRING.relative_to(SOURCE)} imports pycraftcore.mcp_sdk"
    assert [
        violation for violation in _violations(SOURCE / "bootstrap", MCP_SDK) if violation != wiring
    ] == []


def test_nothing_imports_the_source_folder_as_a_package() -> None:
    assert _violations(SOURCE, {"src"}) == []

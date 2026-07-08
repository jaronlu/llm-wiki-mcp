"""Public package entrypoint for the llm-wiki MCP server."""

__all__ = ["main"]


def main() -> None:
    """Start the MCP server, loading runtime config only at execution time."""

    from .server import main as server_main

    server_main()

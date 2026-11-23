"""Static data exposed through the MCP resource protocol."""

from fastmcp import FastMCP


def register_resources(server: FastMCP) -> None:
    @server.resource("guide://deepcopy", mime_type="text/plain", tags={"deepcopy"})
    def deepcopy_guide() -> str:
        """What the Deepcopy tools can and cannot do."""
        return (
            "The deepcopy_* tools read an IBKR portfolio through the Deepcopy API. "
            "They never place, modify or cancel orders. Start with "
            "deepcopy_get_session: if it fails with 'not ready', the operator must "
            "sign in at the IBKR gateway. Then use deepcopy_list_accounts to get "
            "account IDs for the summary and positions tools."
        )

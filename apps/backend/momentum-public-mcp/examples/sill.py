# /// script
# requires-python = ">=3.12"
# dependencies = ["fastmcp==4.2.0a2"]
# ///
"""Standalone Skills example: uv run --script examples/sill.py.

SkillCatalogProvider requires the experimental FastMCP 4.2 API. The inline
dependency runs this example separately from the public server's FastMCP 4.1.3.
"""

from fastmcp import FastMCP, Skill
from fastmcp.skills.provider import SkillCatalogProvider

release_notes = Skill(
    name="release-notes",
    description="Write release notes from merged pull requests.",
    instructions="# Release notes\n\nGroup changes by theme. Follow template.md.\n",
    files={"template.md": "## Highlights\n\n## Fixes\n"},
)

mcp = FastMCP("Team Skills")
mcp.add_provider(SkillCatalogProvider([release_notes]))

if __name__ == "__main__":
    mcp.run()

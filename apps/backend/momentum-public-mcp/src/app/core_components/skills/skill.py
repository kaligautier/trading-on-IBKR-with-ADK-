from fastmcp import Skill

release_notes = Skill(
    name="release-notes",
    description="Write release notes from merged pull requests.",
    instructions="# Release notes\n\nGroup changes by theme. Follow template.md.\n",
    files={"template.md": "## Highlights\n\n## Fixes\n"},
)

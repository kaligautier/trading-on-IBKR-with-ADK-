"""Load plain-text prompt instructions shipped with this package."""

from importlib.resources import files

from momentum_public_mcp.errors import InstructionError


def get_instruction(name: str) -> str:
    """Read an instruction file without rendering or substituting variables."""
    try:
        return (
            files("momentum_public_mcp.mcp.prompts")
            .joinpath("templates", f"{name}.md")
            .read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError) as error:
        raise InstructionError(details={"instruction": name}) from error

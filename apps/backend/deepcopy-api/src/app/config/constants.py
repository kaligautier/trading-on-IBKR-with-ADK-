"""Application constants."""

from app.instructions.instructions_manager import InstructionsManager

instructions_manager = InstructionsManager()

SINGLE_AGENT_DESCRIPTION = """
Read-only Deepcopy agent that answers questions about an IBKR portfolio.
"""

SINGLE_AGENT_INSTRUCTION = instructions_manager.get_instructions("agent_instruction")

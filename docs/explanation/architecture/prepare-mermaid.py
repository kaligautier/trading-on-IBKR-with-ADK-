"""Normalize Structurizr's SVG edge style before Mermaid rendering.

The exported white path fill obscures nodes with ELK's orthogonal routing.
Keep node and relationship content unchanged; never fill connection paths.
"""

from pathlib import Path

for source in sorted(Path(__file__).parent.joinpath("diagrams").glob("*.mmd")):
    text = source.read_text()
    text = text.replace(
        "linkStyle default fill:#ffffff",
        "linkStyle default fill:none,stroke:#627d94,stroke-width:1.5px",
    )
    source.write_text(text)

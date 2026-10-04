"""The Rich text of numbers, for the tables and the form; no Textual."""

from rich.text import Text


def right(text: str, style: str = "") -> Text:
    """text aligned to the right of its column, as numbers are."""
    return Text(text, style=style, justify="right")


def signed(value: float | None, text: str, palette: dict[str, str]) -> Text:
    """text aligned right, in green when value is above 0, in red below, as is at 0 or None."""
    color = palette["green"] if value and value > 0 else palette["red"] if value and value < 0 else ""
    return right(text, color)

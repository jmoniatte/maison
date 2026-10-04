from typing import TypeVar

from textual.widget import Widget

W = TypeVar("W", bound=Widget)


def click_only(widget: W) -> W:
    """widget, which a click must not give focus to, so the view keeps it for its keys."""
    widget.can_focus = False
    return widget

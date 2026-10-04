"""The table both Money pages draw their rows in."""

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.coordinate import Coordinate
from textual.strip import Strip
from textual.widgets import DataTable, Static

# Blank columns between the rows and the scrollbar, so the cursor's shade stops short of it
SCROLLBAR_GAP = 2


def column_widths(labels: list[Text], rows: list[tuple]) -> list[int]:
    """Each column's width, cell padding aside: its label's or its widest cell's."""
    return [max([label.cell_len, *(cell_len(str(row[index])) for row in rows)]) for index, label in enumerate(labels)]


def table_width(widths: list[int]) -> int:
    """How wide MoneyTable.fill makes a table with these column widths."""
    return sum(width + 2 for width in widths)


def padded(cell: Text | str, width: int) -> Text:
    """cell laid out in width, a space each side. Done here to the exact width, since Rich drops the
    trailing spaces of a cell it justifies."""
    text = cell.copy() if isinstance(cell, Text) else Text(cell)
    text.align(text.justify or "left", width - 2)
    result = Text(" ", no_wrap=True)
    result.append_text(text)
    result.append(" ")
    return result


class SectionTitle(Static):
    """A yellow line with a name in it, "── Joint ────", over a table and as wide as it."""

    def __init__(self, label: str, width: int) -> None:
        name = f"── {label} "
        super().__init__(name + "─" * max(width - len(name), 2))


class MoneyTable(DataTable):
    """A table of rows to pick, with Enter or a click, then maybe a footer, such as totals, under a line
    of dashes, which the cursor skips; with dashes_under_labels, a line of dashes under the labels too.
    The cursor follows the pointer, so the mouse and the keys move the same shaded row, and the cells
    keep their colors under it."""

    def __init__(self, dashes_under_labels: bool = False, **kwargs) -> None:
        # cell_padding 0: fill pads the cells itself, so its dashes run across the whole table, gaps included.
        # The cells' own colors win over the cursor's, so a return stays green or red under it
        super().__init__(
            cursor_type="row",
            header_height=2 if dashes_under_labels else 1,
            zebra_stripes=False,
            cell_padding=0,
            cursor_foreground_priority="renderable",
            **kwargs,
        )
        self.dashes_under_labels = dashes_under_labels
        self._pickable = 0

    def fill(self, labels: list[Text], rows: list[tuple], footer: list[tuple] = (), widths: list[int] | None = None) -> None:
        """Replace the columns and rows, the footer's under a line of dashes across the table. widths, when
        given, lines the columns up with another table's."""
        self.clear(columns=True)
        self._pickable = len(rows)
        padded_widths = [width + 2 for width in widths or column_widths(labels, [*rows, *footer])]
        for label, width in zip(labels, padded_widths):
            header = padded(label, width)
            if self.dashes_under_labels:
                header.append("\n" + "-" * width)
            self.add_column(header, width=width)
        self.add_rows(tuple(padded(cell, width) for cell, width in zip(row, padded_widths)) for row in rows)
        if footer:
            self.add_row(*(Text("-" * width, style=self.app.palette["comment"]) for width in padded_widths))
            self.add_rows(tuple(padded(cell, width) for cell, width in zip(row, padded_widths)) for row in footer)

    def render_line(self, y: int) -> Strip:
        # DataTable stretches the cursor's shade up to the scrollbar; padding would go right of the bar
        width = self.scrollable_content_region.width
        line = super().render_line(y)
        if self.show_vertical_scrollbar:
            line = line.crop(0, width - SCROLLBAR_GAP).extend_cell_length(width, self.rich_style)
        return line

    @property
    def pickable_rows(self) -> int:
        """How many rows, from the top, the cursor can be on: all but the footer and its dashes."""
        return self._pickable

    def validate_cursor_coordinate(self, value: Coordinate) -> Coordinate:
        row, column = super().validate_cursor_coordinate(value)
        return Coordinate(min(row, self.pickable_rows - 1) if self.pickable_rows else row, column)

    def row_under(self, event: events.MouseEvent) -> int | None:
        """The row under the pointer that the cursor can be on; None elsewhere, the labels included."""
        row = event.style.meta.get("row")
        return row if isinstance(row, int) and 0 <= row < self.pickable_rows else None

    async def _on_click(self, event: events.Click) -> None:
        # Handled here rather than by DataTable, which selects only on a second click in the same cell, and
        # would move the cursor to the last row it can be on on a click on the labels, the dashes or the footer
        event.prevent_default()
        row = self.row_under(event)
        if row is None:
            return
        event.stop()
        self.focus()
        self.move_cursor(row=row)
        self.action_select_cursor()

    def _on_mouse_move(self, event: events.MouseMove) -> None:
        # In place of DataTable's own hover shade, which Textual would run after this unless prevented
        event.prevent_default()
        self._set_hover_cursor(False)
        row = self.row_under(event)
        if row is None:
            return
        if not self.has_focus:
            self.focus()
        if row != self.cursor_row:
            self.move_cursor(row=row, animate=False)

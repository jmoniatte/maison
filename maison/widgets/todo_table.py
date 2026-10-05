"""The Todos tab's table, as Travail's: the id, the check box and the star, then the date and the name."""

from datetime import date

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DataTable
from tui_kit.shortcuts import ACTIONS

from ..todos import DUE, OVERDUE, Todo, when

# Nerd Font check boxes (nf-md-checkbox_blank_outline, nf-md-checkbox_marked), as Travail's
OPEN_BOX = "\U000f0131"
CLOSED_BOX = "\U000f0132"
PINNED = "★"
UNPINNED = "☆"
# The check box, two spaces, the star
LEAD_WIDTH = 4
# Where the star starts in the lead column, its padding included: a click left of it hits the box
STAR_X = 1 + 2
# The colors of an open todo's state, by palette name; one for later keeps the plain color
STATE_COLORS = {OVERDUE: "red", DUE: "yellow"}


class TodoChangeRequested(Message):
    """A click on a todo's check box (to close or reopen it) or its star (to pin or unpin it)."""

    def __init__(self, todo: Todo, closing: bool) -> None:
        """closing for the box, else the star."""
        super().__init__()
        self.todo = todo
        self.closing = closing


class TodoTable(DataTable):
    """One row per todo, keyed by its id, with no header. A click on the box closes or reopens, on the
    star pins or unpins; anywhere else it opens the todo, as Enter does."""

    BINDINGS = [Binding("enter", "select_cursor", "Open the todo", group=ACTIONS)]

    def __init__(self, **kwargs) -> None:
        super().__init__(cursor_type="row", zebra_stripes=False, show_header=False, cursor_foreground_priority="renderable", **kwargs)
        self.todos: list[Todo] = []
        self.today = date.today()
        # The widest "Tomorrow" or "3 weeks ago" shown, so the names line up
        self.when_width = 0

    def on_mount(self) -> None:
        # As wide as the longest id shown (show), so the rest lines up
        self.add_column("", key="id", width=1)
        self.add_column("", key="lead", width=LEAD_WIDTH)
        self.add_column("", key="todo")

    @property
    def id_width(self) -> int:
        """The id column's width, its padding included."""
        return self.columns["id"].get_render_width(self)

    def show(self, todos: list[Todo], today: date, cursor_on: int | None = None) -> None:
        """Show todos, the cursor on the todo cursor_on names, else on the one it was on, else on the same row."""
        current = cursor_on or (self.todos[self.cursor_row].id if 0 <= self.cursor_row < len(self.todos) else None)
        row = self.cursor_row
        self.today = today
        self.when_width = max((len(when(todo, today)) for todo in todos), default=0)
        self.clear()
        self.todos = list(todos)
        self.columns["id"].width = max((len(str(todo.id)) for todo in todos), default=1)
        for todo in todos:
            self.add_row(Text(str(todo.id), justify="right"), self._lead(todo), self._todo(todo), key=str(todo.id))
        ids = [todo.id for todo in todos]
        if ids:
            self.move_cursor(row=ids.index(current) if current in ids else min(max(row, 0), len(ids) - 1), animate=False)

    def replace(self, todo: Todo) -> None:
        """Show todo's new state in its row, which stays where it is."""
        for index, shown in enumerate(self.todos):
            if shown.id == todo.id:
                self.todos[index] = todo
                self.update_cell(str(todo.id), "lead", self._lead(todo))
                self.update_cell(str(todo.id), "todo", self._todo(todo))
                return

    def selected(self) -> Todo | None:
        return self.todos[self.cursor_row] if 0 <= self.cursor_row < len(self.todos) else None

    def _lead(self, todo: Todo) -> Text:
        palette = self.app.palette
        text = Text(OPEN_BOX if todo.is_open else CLOSED_BOX, style=palette["comment"])
        text.append("  ")
        text.append(PINNED if todo.pinned else UNPINNED, style=palette["yellow"] if todo.pinned else palette["comment"])
        return text

    def _todo(self, todo: Todo) -> Text:
        """How far the due date is, in the state's color (red past it, yellow due, plain later), then the
        name; all grey once closed."""
        palette = self.app.palette
        if todo.is_open:
            color = palette.get(STATE_COLORS.get(todo.state(self.today), ""), "")
        else:
            color = palette["comment"]
        text = Text(f"{when(todo, self.today):<{self.when_width}}", style=color)
        text.append("  ")
        text.append(todo.name, style="" if todo.is_open else palette["comment"])
        return text

    def on_mouse_move(self, event: events.MouseMove) -> None:
        # The highlight follows the pointer, as it does with the arrow keys
        row = event.style.meta.get("row")
        if isinstance(row, int) and 0 <= row < self.row_count and row != self.cursor_row:
            self.move_cursor(row=row)

    async def _on_click(self, event: events.Click) -> None:
        """A click on the box closes or reopens, on the star pins, by which half of their column it hit:
        a terminal may draw the Nerd Font box wider than its cell, so the cell clicked is not always
        the one the icon was written to. Anywhere else it opens the todo."""
        row = event.style.meta.get("row")
        if not (isinstance(row, int) and 0 <= row < self.row_count):
            return
        event.prevent_default()
        event.stop()
        todo = self.todos[row]
        self.move_cursor(row=row)
        if event.style.meta.get("column") == 1:
            if event.x - self.id_width < STAR_X:
                self.post_message(TodoChangeRequested(todo, closing=True))
            else:
                self.post_message(TodoChangeRequested(todo, closing=False))
        else:
            self.action_select_cursor()

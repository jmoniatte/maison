"""A todo's page, in the list's place: its name, due date and note, then its reminders while open, or
the day it was closed and its outcome."""

from dataclasses import replace
from datetime import date

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, Select, Static, TextArea
from tui_kit.dialog import ConfirmDialog
from tui_kit.shortcuts import ACTIONS, GENERAL

from ..click_only import click_only
from ..todos import Todo
from .reminders import DEFAULT_REMINDER, Reminders

def read_date(field: Input) -> date | None | str:
    """The date in field, None when it is empty, or what is wrong with it."""
    text = field.value.strip()
    try:
        return date.fromisoformat(text) if text else None
    except ValueError:
        return "The date must be like 2026-10-03"


class TodoPage(Vertical):
    """The breadcrumbs, "Todos > Change furnace filter"; the name, due date and note; then, while open,
    the reminders, or, closed, the day and the outcome; then Delete and Save."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save the todo", key_display="ctrl+s", group=ACTIONS),
        Binding("escape", "cancel", "Back to the list", key_display="esc", group=GENERAL),
    ]

    class Saved(Message):
        """The todo to save, its id 0 when new."""

        def __init__(self, todo: Todo) -> None:
            super().__init__()
            self.todo = todo

    class Deleted(Message):
        def __init__(self, todo: Todo) -> None:
            super().__init__()
            self.todo = todo

    class Left(Message):
        """Back to the list, nothing saved."""

    def __init__(self, todo: Todo | None = None, toggled: bool = False) -> None:
        """The page for todo, a new one without; toggled, with its status turned, to close or reopen it."""
        super().__init__(id="todo-page", classes="form -compact")
        self.original = todo or Todo(0, "", due_on=date.today(), reminders=(DEFAULT_REMINDER,))
        # The status Save writes: the list's x and box open the page with it turned
        self.closed = self.original.is_open == toggled

    def compose(self) -> ComposeResult:
        todo = self.original
        with Horizontal(classes="breadcrumbs"):
            yield Static("Todos", id="breadcrumb-todos")
            yield Static(">", classes="breadcrumb-separator")
            yield Static(todo.name if todo.id else "New todo", classes="breadcrumb-current", markup=False)
        with Horizontal(classes="form-row"):
            yield Static("Todo", classes="field-label")
            yield Input(todo.name, placeholder="Paint the office", id="name")
        with Horizontal(classes="form-row"):
            yield Static("Due", classes="field-label")
            yield Input(todo.due_on.isoformat() if todo.due_on else "", placeholder="YYYY-MM-DD, empty for some day", id="due")
        with Horizontal(classes="text-row"):
            yield Static("Note", classes="field-label")
            yield TextArea(todo.note, id="note")
        with Horizontal(classes="form-row reminders-row", id="open-part"):
            yield Static("Reminders", classes="field-label")
            yield Reminders(todo.reminders)
        with Vertical(id="closed-part"):
            with Horizontal(classes="form-row"):
                yield Static("Closed on", classes="field-label")
                yield Input((todo.closed_on or date.today()).isoformat(), placeholder="YYYY-MM-DD", id="closed-on")
            with Horizontal(classes="text-row"):
                yield Static("Outcome", classes="field-label")
                yield TextArea(todo.closed_note, placeholder="How it went: the filter was really dirty", id="outcome")
        yield Static("", id="form-error", markup=False)
        # Under the fields: Delete on the left, away from Save on the right; Escape and "Todos" go back
        with Horizontal(id="dialog-buttons"):
            if todo.id:
                yield click_only(Button("Delete", id="delete-btn", classes="tinted -red"))
            yield Static(classes="spacer")
            yield click_only(Button("Save", id="save-btn", classes="tinted -green"))

    def on_mount(self) -> None:
        self.query_one("#open-part").display = not self.closed
        self.query_one("#closed-part").display = self.closed
        # What the page holds as opened, to tell whether leaving it would lose a change
        self.snapshot = self._snapshot()
        # Closing from the list: how it went is what is left to write
        closing = self.closed and self.original.is_open
        self.query_one("#outcome" if closing else "#name").focus()

    def _snapshot(self) -> tuple:
        """The value of every field the page holds."""
        fields = [field.value for field in self.query(Input).results(Input)] + [area.text for area in self.query(TextArea).results(TextArea)]
        return (*fields, *(select.value for select in self.query(Select).results(Select)))

    def _read(self) -> Todo | str:
        """The todo the page makes, or what is wrong with it."""
        name = self.query_one("#name", Input).value.strip()
        if not name:
            return "Enter what to do"
        due_on = read_date(self.query_one("#due", Input))
        if isinstance(due_on, str):
            return due_on
        note = self.query_one("#note", TextArea).text.strip()
        todo = replace(self.original, name=name, note=note, due_on=due_on)
        if self.closed:
            closed_on = read_date(self.query_one("#closed-on", Input))
            if not isinstance(closed_on, date):
                return closed_on or "Enter when it was closed"
            # Closed, its reminders stay as they were, unshown
            return replace(todo, closed_on=closed_on, closed_note=self.query_one("#outcome", TextArea).text.strip())
        reminders = self.query_one(Reminders).read()
        if isinstance(reminders, str):
            return reminders
        return replace(todo, reminders=reminders, closed_on=None, closed_note="")

    def _show_error(self, error: str) -> None:
        # Hidden while empty, so it leaves no blank row
        line = self.query_one("#form-error", Static)
        line.update(error)
        line.display = bool(error)

    @on(Input.Changed)
    @on(TextArea.Changed)
    @on(Select.Changed)
    def _clear_error(self) -> None:
        self._show_error("")

    @on(Input.Submitted)
    @on(Button.Pressed, "#save-btn")
    def action_save(self) -> None:
        read = self._read()
        if isinstance(read, str):
            self._show_error(read)
            return
        self.post_message(self.Saved(read))

    @on(events.Click, "#breadcrumb-todos")
    def action_cancel(self) -> None:
        """Back to the list; with changes made, once confirmed."""
        if self._snapshot() == self.snapshot:
            self.post_message(self.Left())
            return
        dialog = ConfirmDialog("Discard your changes?", title="Unsaved changes", confirm_label="Discard", cancel_label="Keep editing")
        self.app.push_screen(dialog, self._discard)

    def _discard(self, confirmed: bool) -> None:
        if confirmed:
            self.post_message(self.Left())

    @on(Button.Pressed, "#delete-btn")
    def _delete(self) -> None:
        dialog = ConfirmDialog(f"Delete the todo {self.original.name}?", title="Delete todo", confirm_label="Delete", cancel_label="Keep")
        self.app.push_screen(dialog, self._deleted)

    def _deleted(self, confirmed: bool) -> None:
        if confirmed:
            self.post_message(self.Deleted(self.original))

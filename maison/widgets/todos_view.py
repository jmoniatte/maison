"""The Todos tab: a search over the todos, open ones first, with their status in the search; a todo's
page in the list's place."""

from dataclasses import replace
from datetime import date

from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Select, Static, TabbedContent
from tui_kit.shortcuts import ACTIONS

from ..click_only import click_only
from ..config import Config
from ..todos import (
    ALL,
    DEFAULT_STATUS,
    STATUS_WORD,
    STATUSES,
    Todo,
    delete_todo,
    due_todos,
    load_todos,
    save_todo,
    search,
    set_pinned,
    split_status,
)
from .dashed_rule import DashedRule
from .todo_page import TodoPage
from .todo_table import TodoChangeRequested, TodoTable

LABEL = "Todos"


class TodosView(Vertical):
    """As Travail's Todos: the list, a search box, the status dropdown and New Todo, the count in green,
    a dashed rule, then the todos the search finds, open ones first; the status is in the search
    (is:open, is:closed), and the dropdown only mirrors it. A todo opens on its page, in the list's
    place."""

    BINDINGS = [
        Binding("n", "new", "New todo", group=ACTIONS),
        Binding("x", "toggle_closed", "Close, or reopen", group=ACTIONS),
        Binding("p", "toggle_pin", "Pin, or unpin", group=ACTIONS),
        Binding("space", "toggle_pin", "Pin, or unpin", group=ACTIONS),
        Binding("f", "next_status", "Show open, closed or all", group=ACTIONS),
        Binding("slash", "search", "Search", key_display="/", group=ACTIONS),
    ]
    HELP_BINDINGS = (TodoTable.BINDINGS, BINDINGS, TodoPage.BINDINGS)
    # The list's keys, which do nothing while a todo's page shows
    LIST_ACTIONS = {binding.action for binding in BINDINGS}

    def __init__(self, config: Config) -> None:
        super().__init__(id="todos")
        # The search, is:open or is:closed included: the dropdown only mirrors it
        self.query_text = f"is:{DEFAULT_STATUS}"
        self.status = DEFAULT_STATUS

    def compose(self) -> ComposeResult:
        with Vertical(id="todo-list"):
            with Horizontal(id="todo-controls"):
                # The cursor at the end, so typing adds to the search rather than replaces it
                yield Input(self.query_text, placeholder="Search todos", select_on_focus=False, id="search")
                yield Select(STATUSES, value=DEFAULT_STATUS, allow_blank=False, id="todo-status")
                yield click_only(Button("New Todo", id="btn-new-todo", classes="tinted"))
            yield Static("", id="todo-count")
            yield DashedRule(id="todo-rule")
            yield TodoTable(id="todo-table")

    @property
    def page(self) -> TodoPage | None:
        """The todo's page on show, if any."""
        pages = self.query(TodoPage)
        return pages.first() if pages else None

    def check_action(self, action: str, parameters: tuple) -> bool:
        return not (action in self.LIST_ACTIONS and self.page is not None)

    def on_mount(self) -> None:
        # The count on the tab's label shows from any tab
        self.call_next(self.load)

    def tab_shown(self) -> None:
        self.call_next(self.load)

    def set_colors(self) -> None:
        # The states' colors are baked into the cells
        self.call_next(self.load)

    @property
    def table(self) -> TodoTable:
        return self.query_one(TodoTable)

    def load(self, current: int | None = None) -> None:
        """Read the todos again and list those the search finds, the cursor on the row it was on, or on
        the todo with the id current; count the todos due on the tab's label."""
        database = self.app.database
        if database is None:
            self.display = False
            return
        today = date.today()
        todos = load_todos(database)
        self._count_due(todos, today)
        self.status = split_status(self.query_text)[0]
        # Changed here, not chosen: no message
        selector = self.query_one("#todo-status", Select)
        with selector.prevent(Select.Changed):
            selector.value = self.status
        found = search(todos, self.query_text)
        self.table.show(found, today, current)
        self.query_one("#todo-count", Static).update(self._describe(len(found)))
        # Never while hidden: TabbedContent would switch to this tab. Typing in the search, or on a page,
        # keeps the focus where it is
        if self.app.shown_view is not self:
            return
        if self.page is not None:
            if not self.page.has_focus_within:
                self.page.query_one("#name").focus()
        elif not self.query_one("#search", Input).has_focus:
            self.table.focus()

    def _count_due(self, todos: list[Todo], today: date) -> None:
        """The number of todos due or overdue on the tab's label."""
        due = len(due_todos(todos, today))
        self.app.query_one("#modes", TabbedContent).get_tab("todos-mode").label = f"{LABEL} ({due})" if due else LABEL

    def _describe(self, count: int) -> str:
        """"2 open todos", "1 todo matching 'furnace'", for count todos found."""
        status = "" if self.status == ALL else f" {self.status}"
        text = f"{count}{status} {'todo' if count == 1 else 'todos'}"
        words = split_status(self.query_text)[1]
        return f"{text} matching '{words}'" if words else text

    # -- searching

    def action_search(self) -> None:
        self.query_one("#search", Input).focus()

    @on(Input.Changed, "#search")
    def _search_changed(self, event: Input.Changed) -> None:
        # The list follows the search as it is typed
        event.stop()
        self.query_text = event.value.strip()
        self.load()

    @on(Input.Submitted, "#search")
    def _search_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.table.focus()

    def on_key(self, event: events.Key) -> None:
        # Escape in the search goes back to the list, keeping the search; elsewhere it quits, as on every tab
        if event.key == "escape" and self.query_one("#search", Input).has_focus:
            event.stop()
            self.table.focus()

    def action_next_status(self) -> None:
        values = [value for _, value in STATUSES]
        self.query_one("#todo-status", Select).value = values[(values.index(self.status) + 1) % len(values)]

    @on(Select.Changed, "#todo-status")
    def _status_picked(self, event: Select.Changed) -> None:
        """Put is:open or is:closed first in the search in place of the one there, or none for All."""
        event.stop()
        if event.value == self.status:
            return
        words = [word for word in self.query_text.split() if not STATUS_WORD.fullmatch(word)]
        self.query_text = " ".join([f"is:{event.value}", *words] if event.value != ALL else words)
        search_box = self.query_one("#search", Input)
        with search_box.prevent(Input.Changed):
            search_box.value = self.query_text
        self.load()
        self.table.focus()

    # -- changing todos

    @on(TodoTable.RowSelected)
    def _selected(self, event: TodoTable.RowSelected) -> None:
        event.stop()
        self.open_page(self.table.todos[event.cursor_row])

    @on(Button.Pressed, "#btn-new-todo")
    def action_new(self) -> None:
        self.open_page(None)

    def action_toggle_closed(self) -> None:
        if (todo := self.table.selected()) is not None:
            self.open_page(todo, toggled=True)

    def action_toggle_pin(self) -> None:
        if (todo := self.table.selected()) is not None:
            self._pin(todo)

    @on(TodoChangeRequested)
    def _change_requested(self, event: TodoChangeRequested) -> None:
        event.stop()
        if event.closing:
            self.open_page(event.todo, toggled=True)
        else:
            self._pin(event.todo)

    def _pin(self, todo: Todo) -> None:
        """Pin or unpin todo in its row, which moves nothing."""
        set_pinned(self.app.database, todo, not todo.pinned)
        self.table.replace(replace(todo, pinned=not todo.pinned))
        self.notify("Unpinned" if todo.pinned else "Pinned")

    def open_page(self, todo: Todo | None, toggled: bool = False) -> None:
        """Show todo's page, a new one's for None, in the list's place; toggled, to close or reopen it."""
        self.query_one("#todo-list").display = False
        self.mount(TodoPage(todo, toggled))

    async def _close_page(self, current: int | None = None) -> None:
        """Back to the list, read again, its cursor on the todo with the id current."""
        await self.page.remove()
        self.query_one("#todo-list").display = True
        self.load(current)
        self.table.focus()

    @on(TodoPage.Saved)
    async def _saved(self, event: TodoPage.Saved) -> None:
        event.stop()
        todo = event.todo
        todo_id = save_todo(self.app.database, todo)
        await self._close_page(todo_id)
        self.notify(f"Todo {'saved' if todo.id else 'added'}: {todo.name}")

    @on(TodoPage.Deleted)
    async def _deleted(self, event: TodoPage.Deleted) -> None:
        event.stop()
        delete_todo(self.app.database, event.todo)
        await self._close_page()
        self.notify(f"Todo deleted: {event.todo.name}")

    @on(TodoPage.Left)
    async def _left(self, event: TodoPage.Left) -> None:
        event.stop()
        await self._close_page()

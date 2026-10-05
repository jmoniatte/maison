"""Todos, their reminders, searching them, and their writes; no Textual."""

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta

OPEN = "open"
CLOSED = "closed"
ALL = "all"
# The status dropdown's choices; the search starts with is:open
STATUSES = (("Open", OPEN), ("Closed", CLOSED), ("All", ALL))
DEFAULT_STATUS = OPEN
# is:open or is:closed in a search, as on GitHub
STATUS_WORD = re.compile(r"is:(?P<status>open|closed)", re.IGNORECASE)
# An open todo's state, by how near its due date is
OVERDUE = "overdue"
DUE = "due"
LATER = "later"
# Each unit a length is typed in, by its days, the largest last; every length is stored in days
UNITS = {"days": 1, "weeks": 7, "months": 30, "years": 365}


@dataclass(frozen=True)
class Todo:
    """Something to do, by due_on when it has one, open until closed_on, with its outcome (closed_note),
    how it went, and pinned or not. reminders are how many days before due_on to warn about it, the earliest first."""

    id: int
    name: str
    note: str = ""
    due_on: date | None = None
    reminders: tuple[int, ...] = ()
    closed_on: date | None = None
    closed_note: str = ""
    pinned: bool = False

    @property
    def is_open(self) -> bool:
        return self.closed_on is None

    def state(self, today: date) -> str:
        """OVERDUE after its due date, DUE from its earliest reminder or on its due date, LATER before,
        with no due date, or once closed."""
        if self.due_on is None or not self.is_open:
            return LATER
        if today > self.due_on:
            return OVERDUE
        warn_from = self.due_on - timedelta(days=max(self.reminders, default=0))
        return DUE if today >= warn_from else LATER


def due_todos(todos: list[Todo], today: date) -> list[Todo]:
    """The open todos due or overdue."""
    return [todo for todo in todos if todo.state(today) != LATER]


def split_status(query: str) -> tuple[str, str]:
    """The status a search asks for with is:open or is:closed (all without one; the last one wins), and
    the search without it."""
    status, words = ALL, []
    for word in query.split():
        if match := STATUS_WORD.fullmatch(word):
            status = match.group("status").lower()
        else:
            words.append(word)
    return status, " ".join(words)


def search(todos: list[Todo], query: str) -> list[Todo]:
    """The todos of the status query asks for whose name, note or outcome has every word of it, case
    ignored."""
    status, words = split_status(query)
    words = words.lower().split()
    found = []
    for todo in todos:
        if status != ALL and todo.is_open != (status == OPEN):
            continue
        text = f"{todo.name} {todo.note} {todo.closed_note}".lower()
        if all(word in text for word in words):
            found.append(todo)
    return found


def split_length(days: int) -> tuple[int, str]:
    """days as a number and a unit, the largest that divides it evenly, as the form shows it: 180 is
    (6, "months"), 10 (10, "days")."""
    for unit, size in reversed(UNITS.items()):
        if days and days % size == 0:
            return days // size, unit
    return days, "days"


def rough_length(days: int) -> str:
    """days rounded to a unit that reads well: "3 days", "5 weeks", "6 months", "2 years"."""
    if days < 14:
        return plural(days, "days")
    if days < 60:
        return plural(round(days / 7), "weeks")
    if days < 730:
        return plural(round(days / 30), "months")
    return plural(round(days / 365), "years")


def plural(number: int, unit: str) -> str:
    return f"{number} {unit if number != 1 else unit.removesuffix('s')}"


def when(todo: Todo, today: date) -> str:
    """How far a todo's due date is: "Today", "Tomorrow", "2 days", "3 weeks", "Yesterday", "4 days ago";
    "Someday" with none."""
    if todo.due_on is None:
        return "Someday"
    days = (todo.due_on - today).days
    if days in (-1, 0, 1):
        return {-1: "Yesterday", 0: "Today", 1: "Tomorrow"}[days]
    return rough_length(days) if days > 0 else f"{rough_length(-days)} ago"


def _day(text: str | None) -> date | None:
    return date.fromisoformat(text) if text else None


def load_todos(database: sqlite3.Connection) -> list[Todo]:
    """Every todo with its reminders: the open ones first, the soonest first and those with no date last,
    by name; then those closed, the latest first."""
    reminders: dict[int, list[int]] = {}
    for row in database.execute("SELECT todo_id, days_before FROM todo_reminders ORDER BY days_before DESC"):
        reminders.setdefault(row["todo_id"], []).append(row["days_before"])
    todos = [
        Todo(
            row["id"],
            row["name"],
            row["note"] or "",
            _day(row["due_on"]),
            tuple(reminders.get(row["id"], ())),
            _day(row["closed_on"]),
            row["closed_note"] or "",
            bool(row["pinned"]),
        )
        for row in database.execute("SELECT * FROM todos")
    ]
    open_todos = sorted(
        (todo for todo in todos if todo.is_open),
        key=lambda todo: (todo.due_on is None, todo.due_on or date.min, todo.name.lower(), todo.id),
    )
    closed = sorted((todo for todo in todos if not todo.is_open), key=lambda todo: (todo.closed_on, todo.id), reverse=True)
    return open_todos + closed


def save_todo(database: sqlite3.Connection, todo: Todo) -> int:
    """Record todo with its reminders (new when its id is 0), and give its id. A reminder that stays,
    on the same due date, keeps whether it was emailed; any other can fire again."""
    fields = (
        todo.name,
        todo.note,
        todo.due_on.isoformat() if todo.due_on else None,
        todo.closed_on.isoformat() if todo.closed_on else None,
        todo.closed_note,
        todo.pinned,
    )
    with transaction(database):
        emailed = {}
        if todo.id:
            before = database.execute("SELECT due_on FROM todos WHERE id = ?", (todo.id,)).fetchone()
            same_due = before["due_on"] == fields[2]
            if same_due:
                emailed = dict(database.execute("SELECT days_before, emailed_on FROM todo_reminders WHERE todo_id = ?", (todo.id,)).fetchall())
            database.execute(
                "UPDATE todos SET name = ?, note = ?, due_on = ?, closed_on = ?, closed_note = ?, pinned = ? WHERE id = ?", (*fields, todo.id)
            )
            if not same_due:
                # A new date is emailed again when it comes
                database.execute("UPDATE todos SET due_emailed_on = NULL WHERE id = ?", (todo.id,))
            database.execute("DELETE FROM todo_reminders WHERE todo_id = ?", (todo.id,))
            todo_id = todo.id
        else:
            todo_id = database.execute(
                "INSERT INTO todos (name, note, due_on, closed_on, closed_note, pinned) VALUES (?, ?, ?, ?, ?, ?)", fields
            ).lastrowid
        database.executemany(
            "INSERT INTO todo_reminders (todo_id, days_before, emailed_on) VALUES (?, ?, ?)",
            ((todo_id, days, emailed.get(days)) for days in todo.reminders),
        )
    return todo_id


def delete_todo(database: sqlite3.Connection, todo: Todo) -> None:
    with transaction(database):
        database.execute("DELETE FROM todo_reminders WHERE todo_id = ?", (todo.id,))
        database.execute("DELETE FROM todos WHERE id = ?", (todo.id,))


def set_pinned(database: sqlite3.Connection, todo: Todo, pinned: bool) -> None:
    database.execute("UPDATE todos SET pinned = ? WHERE id = ?", (pinned, todo.id))


@dataclass(frozen=True)
class Notice:
    """What a todo's email is for: the reminders whose day has come, and whether its due date has."""

    todo_id: int
    reminder_ids: tuple[int, ...]
    due: bool


def to_email(database: sqlite3.Connection, today: date) -> list[Notice]:
    """The open todos with something to email today, by id: reminders and due dates whose day is today,
    even if already emailed, so every run sends them; and those whose day has passed and that were never
    emailed, missed by the runs before."""
    reminders: dict[int, list[int]] = {}
    for row in database.execute(
        """
        SELECT todo_reminders.id, todo_id, date(due_on, '-' || days_before || ' days') AS day
        FROM todo_reminders JOIN todos ON todos.id = todo_id
        WHERE closed_on IS NULL AND (day = ? OR (day < ? AND emailed_on IS NULL))
        """,
        (today.isoformat(), today.isoformat()),
    ):
        reminders.setdefault(row[1], []).append(row[0])
    due = {
        row[0]
        for row in database.execute(
            "SELECT id FROM todos WHERE closed_on IS NULL AND (due_on = ? OR (due_on < ? AND due_emailed_on IS NULL))",
            (today.isoformat(), today.isoformat()),
        )
    }
    return [Notice(todo_id, tuple(reminders.get(todo_id, ())), todo_id in due) for todo_id in sorted(set(reminders) | due)]


def mark_emailed(database: sqlite3.Connection, notice: Notice, today: date) -> None:
    """notice's reminders, and its due date when it was for it, emailed today."""
    with transaction(database):
        database.executemany("UPDATE todo_reminders SET emailed_on = ? WHERE id = ?", ((today.isoformat(), id) for id in notice.reminder_ids))
        if notice.due:
            database.execute("UPDATE todos SET due_emailed_on = ? WHERE id = ?", (today.isoformat(), notice.todo_id))


@contextmanager
def transaction(database: sqlite3.Connection) -> Iterator[None]:
    """The block's writes as one: the connection commits each statement on its own otherwise."""
    database.execute("BEGIN")
    try:
        yield
    except BaseException:
        database.execute("ROLLBACK")
        raise
    database.execute("COMMIT")

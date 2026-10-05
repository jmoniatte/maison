"""A todo's reminders on its page, one row each: a length before its due date, as a number and a unit."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Select, Static

from ..todos import UNITS, split_length

# A new todo's reminder
DEFAULT_REMINDER = 7


class ReminderRow(Horizontal):
    """One reminder: a number and a unit, "before", and a button to remove it. The number may be left
    empty."""

    def __init__(self, days: int | None) -> None:
        super().__init__(classes="reminder-row")
        self.days = days

    def compose(self) -> ComposeResult:
        number, unit = split_length(self.days) if self.days is not None else ("", "months")
        yield Input(str(number), classes="length-number")
        yield Select([(name, name) for name in UNITS], value=unit, allow_blank=False, classes="length-unit")
        yield Static("before", classes="length-after")
        yield Button("Remove", classes="tinted -red remove-reminder")

    def read(self) -> int | None | str:
        """The length in days, None when the number is empty, or what is wrong with it."""
        text = self.query_one(".length-number", Input).value.strip()
        if not text:
            return None
        if not text.isdigit():
            return "Lengths must be whole numbers, such as 3"
        return int(text) * UNITS[self.query_one(".length-unit", Select).value]


class Reminders(Vertical):
    """A todo's reminders, one row each, then Add reminder."""

    def __init__(self, reminders: tuple[int, ...]) -> None:
        super().__init__(id="reminders")
        self.reminders = reminders

    def compose(self) -> ComposeResult:
        for days in self.reminders:
            yield ReminderRow(days)
        yield Button("Add reminder", id="add-reminder", classes="tinted")

    def read(self) -> tuple[int, ...] | str:
        """The reminders in days, the earliest first, those with no number left out; or what is wrong."""
        reminders = set()
        for row in self.query(ReminderRow).results(ReminderRow):
            days = row.read()
            if isinstance(days, str):
                return days
            if days is not None:
                reminders.add(days)
        return tuple(sorted(reminders, reverse=True))

    @on(Button.Pressed, "#add-reminder")
    async def _add(self, event: Button.Pressed) -> None:
        event.stop()
        row = ReminderRow(None)
        await self.mount(row, before="#add-reminder")
        row.query_one(Input).focus()

    @on(Button.Pressed, ".remove-reminder")
    async def _remove(self, event: Button.Pressed) -> None:
        event.stop()
        await event.button.parent.remove()

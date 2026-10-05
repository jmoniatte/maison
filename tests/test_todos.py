import sqlite3
import unittest
from dataclasses import replace
from datetime import date, timedelta

from maison.database import migrate
from maison.todos import (
    ALL,
    DUE,
    LATER,
    OPEN,
    OVERDUE,
    Todo,
    delete_todo,
    due_todos,
    load_todos,
    Notice,
    mark_emailed,
    save_todo,
    search,
    set_pinned,
    split_length,
    split_status,
    to_email,
    when,
)

TODAY = date(2026, 10, 4)


def days(count: int) -> date:
    return TODAY + timedelta(days=count)


class TodosTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = sqlite3.connect(":memory:", isolation_level=None)
        self.database.row_factory = sqlite3.Row
        self.addCleanup(self.database.close)
        migrate(self.database)

    def test_lengths_take_the_largest_unit_and_due_dates_read_as_how_far(self) -> None:
        self.assertEqual([split_length(n) for n in (730, 365, 90, 21, 10, 0)], [(2, "years"), (1, "years"), (3, "months"), (3, "weeks"), (10, "days"), (0, "days")])
        self.assertEqual(
            [when(Todo(1, "", due_on=days(n)), TODAY) for n in (-30, -4, -1, 0, 1, 2, 10, 30, 183, 800)],
            ["4 weeks ago", "4 days ago", "Yesterday", "Today", "Tomorrow", "2 days", "10 days", "4 weeks", "6 months", "2 years"],
        )
        self.assertEqual(when(Todo(1, "Paint"), TODAY), "Someday")

    def test_a_todo_is_due_from_its_earliest_reminder_and_overdue_after_its_date(self) -> None:
        passport = Todo(1, "Passport", due_on=days(150), reminders=(180, 150))
        self.assertEqual(passport.state(TODAY), DUE)
        self.assertEqual(passport.state(days(-31)), LATER)
        self.assertEqual(passport.state(days(151)), OVERDUE)
        # With no reminder, due on the day only; with no date, or closed, never
        self.assertEqual([Todo(1, "", due_on=TODAY).state(day) for day in (days(-1), TODAY)], [LATER, DUE])
        self.assertEqual(Todo(1, "Paint").state(TODAY), LATER)
        self.assertEqual(replace(passport, closed_on=TODAY).state(days(151)), LATER)

    def test_a_search_keeps_the_status_it_asks_for_and_every_word(self) -> None:
        self.assertEqual(split_status("is:open furnace"), (OPEN, "furnace"))
        self.assertEqual(split_status("furnace IS:CLOSED is:open"), (OPEN, "furnace"))
        self.assertEqual(split_status("furnace"), (ALL, "furnace"))
        todos = [
            Todo(1, "Change furnace filter", "16x25"),
            Todo(2, "Change furnace filter", closed_on=TODAY, closed_note="really dirty"),
            Todo(3, "Paint the office"),
        ]
        self.assertEqual([todo.id for todo in search(todos, "is:open")], [1, 3])
        self.assertEqual([todo.id for todo in search(todos, "is:closed")], [2])
        self.assertEqual([todo.id for todo in search(todos, "Furnace")], [1, 2])
        self.assertEqual([todo.id for todo in search(todos, "furnace 16x25")], [1])
        self.assertEqual([todo.id for todo in search(todos, "dirty")], [2])

    def test_todos_are_saved_closed_reopened_and_deleted(self) -> None:
        filter_id = save_todo(self.database, Todo(0, "Filter", "16x25", days(-3), (14, 7)))
        save_todo(self.database, Todo(0, "Paint the office"))
        passport_id = save_todo(self.database, Todo(0, "Passport", due_on=days(150), reminders=(180,)))
        # The soonest first, those with no date last
        todos = load_todos(self.database)
        self.assertEqual([(todo.name, todo.reminders) for todo in todos], [("Filter", (14, 7)), ("Passport", (180,)), ("Paint the office", ())])
        self.assertEqual(len(due_todos(todos, TODAY)), 2)

        # Closed, it comes after the open ones, with how it went; a closed todo can be changed
        save_todo(self.database, replace(todos[0], closed_on=TODAY, closed_note="really dirty"))
        save_todo(self.database, replace(todos[1], closed_on=days(-1)))
        closed = load_todos(self.database)[1:]
        self.assertEqual([(todo.id, todo.closed_on, todo.closed_note) for todo in closed], [(filter_id, TODAY, "really dirty"), (passport_id, days(-1), "")])
        save_todo(self.database, replace(closed[0], closed_on=days(1), closed_note="dirty"))
        self.assertEqual((load_todos(self.database)[1].closed_on, load_todos(self.database)[1].closed_note), (days(1), "dirty"))
        # Reopened, it is open again, with no closing
        save_todo(self.database, replace(closed[0], closed_on=None, closed_note=""))
        reopened = load_todos(self.database)[0]
        self.assertEqual((reopened.id, reopened.is_open, reopened.closed_note), (filter_id, True, ""))

        # Pinned or not, as it is saved
        set_pinned(self.database, reopened, True)
        self.assertTrue(load_todos(self.database)[0].pinned)
        save_todo(self.database, replace(load_todos(self.database)[0], pinned=False))
        self.assertFalse(load_todos(self.database)[0].pinned)

        # Deleting a todo deletes its reminders
        delete_todo(self.database, reopened)
        self.assertEqual([todo.name for todo in load_todos(self.database)], ["Paint the office", "Passport"])
        self.assertEqual(self.database.execute("SELECT count(*) FROM todo_reminders").fetchone()[0], 1)

    def notices(self, today: date) -> list[tuple[int, int, bool]]:
        """What to email today: each todo's id, its number of reminders, and whether for its due date."""
        return [(notice.todo_id, len(notice.reminder_ids), notice.due) for notice in to_email(self.database, today)]

    def test_reminders_and_due_dates_are_emailed_on_their_day_and_once_after(self) -> None:
        todo_id = save_todo(self.database, Todo(0, "Passport", due_on=days(150), reminders=(180, 150, 30)))
        todo = load_todos(self.database)[0]
        # Two reminders have come, 180 days before (passed) and 150 (today): one notice for the todo
        self.assertEqual(to_email(self.database, TODAY), [Notice(todo_id, (1, 2), False)])
        mark_emailed(self.database, to_email(self.database, TODAY)[0], TODAY)
        # Sent, today's (150 days before) goes again on every run today; a passed day's only if never sent
        self.assertEqual(to_email(self.database, TODAY), [Notice(todo_id, (2,), False)])
        self.assertEqual(to_email(self.database, days(1)), [])
        self.assertEqual(to_email(self.database, days(120)), [Notice(todo_id, (3,), False)])
        # The due date, with no reminder left
        mark_emailed(self.database, to_email(self.database, days(120))[0], days(120))
        self.assertEqual(to_email(self.database, days(150)), [Notice(todo_id, (), True)])
        mark_emailed(self.database, to_email(self.database, days(150))[0], days(150))
        self.assertEqual(to_email(self.database, days(150)), [Notice(todo_id, (), True)])
        self.assertEqual(to_email(self.database, days(151)), [])

        # The same date keeps what was emailed, a new reminder whose day has passed can go
        save_todo(self.database, replace(todo, reminders=(180, 160)))
        self.assertEqual(self.notices(days(151)), [(todo_id, 1, False)])
        # A new date and every reminder, and the date itself, can go again
        save_todo(self.database, replace(todo, due_on=days(160), reminders=(180, 160)))
        self.assertEqual(self.notices(days(160)), [(todo_id, 2, True)])
        # A todo with no reminder still has its due date; never one closed, nor one with no date
        other_id = save_todo(self.database, Todo(0, "Filter", due_on=TODAY))
        save_todo(self.database, replace(todo, due_on=days(160), reminders=(180, 160), closed_on=TODAY))
        save_todo(self.database, Todo(0, "Paint", reminders=(7,)))
        self.assertEqual(to_email(self.database, TODAY), [Notice(other_id, (), True)])


if __name__ == "__main__":
    unittest.main()

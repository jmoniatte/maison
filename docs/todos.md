# Todos

The Todos tab keeps track of things to do, as Travail's Todos tab does, with dates: each todo can
be due by a day and warn ahead of it, by email and in the tab. It is the first tab, so `maison`
opens on it (`maison todos`).

A **todo** is a name ("Change furnace filter"), a note ("16x25"), maybe a due date, and
reminders, a number of days before the due date each (6 months before, then 5), as Fastmail's
event alerts do. It can be pinned, as in Travail, a star to spot it by. It is open until closed, with the day it was closed and how it went ("the filter
was really dirty"). Nothing repeats: a chore that comes back is a new todo each time, and a
search on its name ("furnace") finds them all.

`todos.py` holds todos, their search and their writes, with no Textual; `due.py` is `maison due`.
The tab is `TodosView` (`widgets/todos_view.py`), its rows `TodoTable` (`widgets/todo_table.py`);
its page `TodoPage` (`widgets/todo_page.py`), with the reminders in
`widgets/reminders.py`.

## Data

Migration 5 adds two tables:

```sql
CREATE TABLE todos (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,            -- "Change furnace filter"
  note TEXT,                     -- "16x25"
  due_on DATE,                   -- NULL: some day
  closed_on DATE,                -- NULL while open
  closed_note TEXT,              -- the outcome: how it went
  pinned INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE todo_reminders (
  id INTEGER PRIMARY KEY,
  todo_id INTEGER NOT NULL,
  days_before INTEGER NOT NULL,  -- 180, 7; 0: on the due date
  emailed_on DATE                -- NULL until its email is sent
);
```

A todo is open while `closed_on` is NULL.

## Lengths

A reminder's length is stored in days. The form takes a number and a unit: days, weeks, months or
years, a week 7 days, a month 30 and a year 365 (`UNITS`). They show in the largest unit that
divides them evenly, else in days (`split_length`): 365 is 1 year, 180 6 months, 14 2 weeks, 10
10 days. So a length opens in the form as it was typed.

How far a due date is (`when`) is "Today", "Tomorrow" or "Yesterday", else rounded to the unit that
reads best (`rough_length`): "2 days", "5 months", "3 days ago"; "Someday" with no date.

## A todo's state

An open todo is (`Todo.state`):

- **overdue**, in red, once today is after `due_on`
- **due**, in yellow, from its earliest reminder (`due_on - days_before`), or on its due date
- **later**, in the plain color, before that, or with no due date

The tab's label shows how many todos are due or overdue: "Todos (2)", and "Todos" alone with
none. `TodosView` counts them on mount, so the label is right from any tab, and each time it
reads the todos.

## The list

As Travail's Todos tab: a boxed search box, the status dropdown (Open, Closed, All) and New Todo,
the count in green ("3 open todos", "1 todo matching 'furnace'"), a dashed rule (`DashedRule`),
then `TodoTable`, which has no header, a row per todo the search finds. A row is the id, right
aligned; the check box (Nerd Font `󰄱`, `󰄲` once closed) and the star (`☆`, `★` in yellow once
pinned), grey; then how far the due date is ("Tomorrow", "2 days", "3 days ago", "Someday"),
padded to the widest shown so the names line up, in the open todo's state's color: red past it,
yellow due, plain later; and the name. A closed todo's are grey. The open ones come first, the soonest first and
those with no date last, by name; then the closed ones, the latest first. Pinned todos are not
sorted apart, as in Travail. With nothing found, the table is empty and the count says 0.

The status is in the search, as on GitHub: `is:open` (the search starts with it) or `is:closed`,
and none for all (`todos.split_status`; the last one wins). The dropdown only mirrors it: picking
a status, or `f`, puts `is:open` or `is:closed` first in the search in place of the one there, or
takes it out for All. A search keeps the todos whose name, note or outcome has every other
word, case ignored (`todos.search`). The list follows the search as it is typed.

`TodosView` holds the list (`TodoList`) and, in its place while one is open, a todo's page
(`TodoPage`). It reads the todos each time the tab shows, on a theme change (the colors are baked
into the cells), and after each change. It alone writes to the database. Keys on the list: Enter
or a click on a row opens the todo's page, `n` (or New Todo) a new one's, `x` opens the page to
close the todo, or reopen a closed one, `p` or space pins or unpins it, `f` goes round Open,
Closed and All, `/` goes to the search (Enter or Escape go back to the list, keeping it). Escape
elsewhere quits, as on every tab. A click on the box does what `x` does, on the star what `p`
does, by which half of their column it hit, since a terminal may draw the Nerd Font box wider
than its cell. As in Travail, pinning changes the row where it is and moves nothing.

## A todo's page

`TodoPage` takes the list's place, with room for a note on many lines. First the breadcrumbs,
"Todos > Change furnace filter" ("Todos > New todo" for a new one), "Todos" a link back. Then the todo's fields,
in the forms' style (grey labels, fields with no box but a
line under them, blue when focused, no blank row between them): Todo (the name), Due (today for a
new one; empty for some day), and Note, a box two lines tall that grows with what is written, up to ten.

Then, while the todo is open, its reminders, one row each, a number, a unit and "before", with a
Remove button, and Add reminder under them (a new todo starts with 1 week before; a reminder left
with no number is dropped). While it is closed, or being closed, Closed on (today when just
closed) and Outcome, how it went, a box like Note's, in their place. The page has no box or
star: the list closes, reopens and pins. Opened from the list's `x` or box, the page has the status
already turned, which Save writes, the Outcome focused when closing.

Under the fields, on one row: Delete (red, not for a new todo) on the left, away from Save (green)
on the right. There is no Cancel: Escape and "Todos" go back.

Save, or `ctrl+s`, checks the fields and says in red under them what is wrong (a missing name, a
date not like 2026-10-03, a length that is not a whole number), then saves and goes back to the
list, its cursor on the todo. Escape or "Todos" go back without saving; with changes made,
they ask first with tui-kit's `ConfirmDialog` ("Discard your changes?"), whose Keep editing has
focus. Delete asks first the same way. Saving keeps whether a reminder was emailed when it stays
on the same due date; a new reminder, or a new date, can email again; a todo closed keeps its
reminders, unshown.

## Email

`maison due` prints the todos due or overdue, a line each (date, name, how far), and nothing
when there are none, so it can run when a shell starts. `maison due --email` emails the
reminders instead. Neither needs a terminal, so `__main__` runs them before tui-kit's terminal
check.

A reminder fires once (`fired_reminders`): `maison due --email` looks for reminders of open todos
whose day has come and whose `emailed_on` is NULL. With none, it sends nothing. With some, it
sends one email: the todos they warn about under "Coming up", then every overdue todo under
"Overdue", so an overdue todo is not forgotten; then it sets their `emailed_on` to today. If the
sending fails, nothing is set, and the next run tries again. A reminder whose day was already
past when it was added fires on the next run.

It sends through SMTP over SSL with the standard library's `smtplib`, set in the config:

```yaml
email:
  to: me@fastmail.com
  from: me@fastmail.com
  password: an app password      # Fastmail: Settings > Privacy & Security > App passwords
  username: me@fastmail.com      # the default: from
  smtp_host: smtp.fastmail.com   # the default
  smtp_port: 465                 # the default
```

`to`, `from` and `password` are needed; without them the footer, and `maison due`, warn that
emails are off, and `maison due --email` exits with an error.

It runs each morning from a systemd user timer, on one computer only: the database is shared
through Dropbox, so a timer on each would send each email once per computer.

```ini
# ~/.config/systemd/user/maison-due.service
[Service]
Type=oneshot
ExecStart=%h/.local/bin/maison due --email

# ~/.config/systemd/user/maison-due.timer
[Timer]
OnCalendar=*-*-* 08:00
Persistent=true

[Install]
WantedBy=timers.target
```

`systemctl --user enable --now maison-due.timer` turns it on. `Persistent=true` runs a missed
morning when the computer wakes.

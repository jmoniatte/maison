# Reminders

Not built yet: this is the spec.

The Reminders tab keeps track of things to do by a date: chores that come back (change the
furnace filter every 3 months) and things that expire (renew a passport). Each task can warn
several times before its date, as Fastmail's event alerts do (6 months before, then 5), by email
and in the tab. It is `maison reminders`, the second entry in `MODES`.

## Data

Migration 5 adds two tables:

```sql
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  due_on DATE NOT NULL,
  repeat_days INTEGER,
  status TEXT NOT NULL DEFAULT 'open',
  done_on DATE,
  previous_id INTEGER,
  note TEXT
);

CREATE TABLE task_reminders (
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL,
  days_before INTEGER NOT NULL,
  emailed_on DATE
);
```

- `tasks`: one thing to do by one date. `name` says what ("Renew passport (Claire)"),
  `repeat_days` how long after it is done the next one is due (NULL: it does not repeat),
  `status` is `open` or `done`, `done_on` the day it was done, `note` anything (a Dropbox path,
  the filter's size). `previous_id` is the task this one repeats, so a chain of them is its
  history.
- `task_reminders`: when to warn about a task, `days_before` its due date (0: on the day).
  `emailed_on` is the day its email went out, NULL until then.

There is no separate history table: a task done is a row with `status = 'done'`.

## Lengths

Every length (a repeat, a reminder) is stored in days. The form takes a number and a unit:
days, weeks, months or years, a week 7 days, a month 30 and a year 365. They show in the
largest unit that divides them evenly, else in days: 365 is "1 year", 180 "6 months", 14
"2 weeks", 10 "10 days". So a length opens in the form as it was typed (180 as 6 months).

A repeat in days drifts from the calendar ("every month" is every 30 days); the form shows the
next due date, so it can be set right by hand, as for a passport, whose next date is the new
one's expiry.

## A task's state

An open task is:

- **overdue**, in red, once today is after `due_on`
- **due**, in yellow, once its earliest reminder has fired: today is on or after
  `due_on - days_before`
- **later**, in the plain color, before that, or with no reminder at all

The tab's label shows how many tasks are due or overdue: "Reminders (2)", and "Reminders"
alone with none.

## Pages

Two pages, as Money's: the list and one task's page, with the same breadcrumbs ("Reminders",
then "Reminders > Change furnace filter"). Escape, Backspace or "Reminders" go back.

**The list**: a `MoneyTable` of the open tasks, the soonest first: Due (the date), Task, When
("in 3 weeks", "today", "4 days late", in the state's color) and Repeats ("every 3 months", or
empty). A New Task button sits at the right of the breadcrumbs. Enter or a click opens a task.

**A task's page**: its details (Task, Due, Repeats, Note, and its reminders, "6 months, 5
months before"), with Done and Edit buttons at the right of the breadcrumbs, then its history:
the done tasks of its chain, the latest first, with Due, Done and Note. A done task opened from
the history has no Done button.

## The form

`TaskScreen`, in the style of `TransactionScreen`: Task (the name), Due, Repeats (a number and
a unit; empty means it does not repeat), Note, then the reminders, one row each, a number and a
unit and "before", with a button to remove it and one to add another. A new task starts with
one reminder, 1 week before. Save checks the fields: a name, a date like 2026-10-03, whole
numbers above 0 for the repeat and above or at 0 for the reminders. A task being changed has a
red Delete button, which asks first with tui-kit's `ConfirmDialog`.

Changing a reminder's length sets its `emailed_on` back to NULL, so it can fire again.

## Done

Done sets `status` to `done` and `done_on` to today. If the task repeats, a new open task is
added with the same name, repeat, note and reminders (each `emailed_on` NULL), due `done_on +
repeat_days`, its `previous_id` the done task. The page then shows the new task, so its date
can be changed at once.

Deleting a task that a later one repeats gives that later one the deleted task's
`previous_id`, so the chain holds.

## Email

`maison due` prints the due and overdue tasks and quits; it prints nothing when there are none,
so it can run when a shell starts. `maison due --email` sends them by email instead. Neither
needs a terminal, so they run before tui-kit's terminal check.

A reminder fires once: `maison due --email` looks for reminders of open tasks whose date has come
(`due_on - days_before` is today or before) and whose `emailed_on` is NULL. With none, it sends
nothing. With some, it sends one email listing them, then every overdue task, so an overdue
task is not forgotten, and sets their `emailed_on` to today. If the sending fails, nothing is
set, so the next run tries again. A reminder whose date was already past when it was added fires
on the next run.

It sends through SMTP with the standard library's `smtplib` (SSL, port 465), set in the config:

```yaml
email:
  to: me@fastmail.com
  from: me@fastmail.com
  username: me@fastmail.com
  password: an app password      # Fastmail: Settings > Privacy & Security > App passwords
  smtp_host: smtp.fastmail.com   # the default
  smtp_port: 465                 # the default
```

With no `email` section, `maison due --email` says so and exits with an error.

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

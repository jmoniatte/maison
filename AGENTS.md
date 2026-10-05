# maison

TUI with home tools, one tab each: `maison todos` (the default) or `maison money` says which
tab it opens on. Todos keeps track of things to do, with dates and reminders, and emails the reminders
(`maison due --email`). Money keeps track of investment accounts, a port of the fin Ruby gem
(`~/jmoniatte/fin`, the reference for the old behavior).

It is built on [tui-kit](https://github.com/jmoniatte/tui-kit), shared with outils, flotte
and yafyaf-tui: the themes and the picker (`t`), the messages, Help (`?`), the
dialogs, the startup check and the buttons' look (the `tinted` class, with `-green` or `-red`)
all come from there. Put what every app would use in tui-kit, not here; see its AGENTS.md. It is
laid out like outils: no border around the screen and no title bar (tui-kit's `AppHeader`): the
tabs are the first row, and every message, errors included, goes to the footer, in Help's place
(see Modes).

## Rules

- Do not git commit unless asked
- Specs come before code: describe a tab in `docs/<tab>.md` before building it, and read it
  before changing that tab (`docs/money.md`, `docs/todos.md`)
- Keep the shortcuts few: the ones on the Help panel are the whole set
- The help screen lists every binding that has a description and a `group`
  (`tui_kit.shortcuts.ACTIONS` or `GENERAL`) in `MaisonApp.BINDINGS` and in the tab's view's
  `BINDINGS` (or its `HELP_BINDINGS`); document a new key there
- Never hardcode a color in a `.tcss` file

## Run

```bash
maison            # Todos
maison money
maison due        # The todos due; --email emails their reminders
```

It refuses to start unless stdin and stdout are a terminal (tui-kit's `start`); `maison due`
needs none, so a timer can run it.

## Test

Run both from the git root.

```bash
uv run python -m unittest discover -s tests
uv run ruff check .
```

There is no pytest. `ruff` is pinned in the `dev` dependency group, so use `uv run ruff`.
tui-kit comes from GitHub's master (`[tool.uv.sources]`); after a push there,
`uv lock --upgrade-package tui-kit` picks it up. To work on both at once, switch that source to
the commented-out `../tui-kit` path.

## Structure

```
maison/                 # git root + pyproject.toml (run uv commands here)
  maison/               # Python package
    __init__.py         # The version and the repository's URL
    app.py              # MaisonApp, a tui-kit BaseApp: MODES, the footer and its messages, the keys
    __main__.py         # The command line: which tab to open on, or maison due
    config.py           # Optional ~/.config/maison/config.yaml (theme, through tui_kit.config; database_path; email)
    database.py         # The SQLite database: opening it and its migrations; no Textual
    todos.py            # Todos, their reminders, searching them, and their writes; no Textual
    due.py              # maison due: the todos due, printed or emailed; no Textual
    money.py            # Accounts, balances, periods and returns, as fin worked them out, and their writes; no Textual
    cells.py            # right and signed: the Rich text of numbers, for the tables and the form; no Textual
    click_only.py       # click_only: a widget a click does not give focus to
    screens/
      help_screen.py    # MaisonHelpScreen: tui-kit's Help, the app's keys and the tab's own
      transaction_screen.py  # TransactionScreen: the form for a new balance
    widgets/
      todos_view.py     # TodosView, the Todos tab: a search, is:open or is:closed in it, over the todos
      todo_page.py      # TodoPage: one todo, in the list's place: its fields, reminders or outcome
      reminders.py      # Reminders: a todo's reminders on its page, each a number and a unit
      todo_table.py     # TodoTable: a row per todo, as Travail's: the id, the box, the star, how far the due date is and the name
      dashed_rule.py    # DashedRule: a dashed line as wide as the widget
      money_view.py     # MoneyView, the Money tab: loads the accounts, switches between its two pages
      dashboard.py      # Dashboard, the first page: an AccountsTable per owner
      account_page.py   # AccountPage: one account's details, then its transactions, balance chart and returns
      balance_chart.py  # BalanceChart: the balance over time as a braille line
      money_table.py    # MoneyTable, the table both pages use, and SectionTitle
    styles/maison.tcss  # maison's own styles, joined after tui-kit's (app.STYLE_FILES)
  docs/                 # One spec per tab
  tests/
```

## Modes

Each mode is a tab of the `#modes` `TabbedContent`, the first row; the command line picks the
one it opens on. A click on a tab or `tab` switches; `tab` is an app binding with `priority`, so
the screen's own `tab` (focus next) never runs, and it is skipped while a panel or dialog is up.
The tabs cannot take focus. When a tab shows, `MaisonApp._show_mode` gives focus to its view if
it can take it and clears it otherwise, so a hidden view never keeps it. A view must not focus
itself while hidden: `TabbedContent` switches to the tab of whatever has focus. `_show_mode` also
calls `tab_shown` on a view that has it, and `tab_hidden` on the one before
(`MaisonApp.shown_view`). A view that acts when its tab shows or hides uses those, never
`on_show` and `on_hide`, because Textual's partial relayout does not always send Show to a pane
that comes back. `_show_mode` runs twice for the first tab (on mount, then on `TabActivated`), so
it does all this only when the view changes. The panes are `<mode>-mode`, not the view's own id,
which a duplicate would break.

Every tab sits over the same footer: `MaisonApp.compose` adds `#app-footer`, docked at the
bottom, a rule (`border-top`) over Exit, in red, which quits, on the left, and Help, which opens
the shortcuts (as `?` does), on the right (`dock: right`). tui-kit shows messages in whatever
`HeaderNotification` the screen holds, so the footer holds one, `FooterMessage`: while a message
shows, it takes Help's place, right-aligned over the rest of the line (an error wraps onto up to
three lines), and Help comes back once it clears. Exit and Help cannot take focus, so a click
leaves the mode's keys working. Config warnings show there on start.

`MODES` in `app.py` maps each name the command line takes to its tab label and view widget;
the first one is the default. Help (`MaisonHelpScreen`) lists the app's keys under General on
the left, and the tab's own on the right under the tab's name: the view's `BINDINGS`, or its
`HELP_BINDINGS` when it has more (`MaisonApp.action_help` passes the view on show). Each column
is as wide as its longest line and at least General's width (`min-width: 24`). Every view gets
the `mode` class, which gives all tabs the same padding, and takes the `Config`. A new mode is a
view in `widgets/` and an entry in `MODES`; `__main__` offers it on its own.

## Database

The data is in one SQLite file, `~/Dropbox/data/maison.sqlite3` by default (`database_path` in
the config), so every computer sees the same. `MaisonApp.__init__` opens it with
`database.open_database` (the standard library's `sqlite3`), which creates the file and its
folder when missing and runs the migrations it lacks; `app.database` is the connection, closed on
unmount. When it cannot open, `app.database` is None and the error shows in the footer. App tests
always pass a `database_path` in a temporary folder, never the real one.

`database.MIGRATIONS` is a list of SQL scripts, in order; `PRAGMA user_version` is how many of
them a database has run, and each runs with its new number in one transaction. Add a migration
at the end; never edit one that may have run. Before the first change to a database that
existed, it is copied next to itself as `<name>.backup-v<version>.sqlite3`, once per version.
`open_database` sets `journal_mode = DELETE`, as fin did, so there is never a `-wal` file beside
it and Dropbox syncs the database whole.

Migrations 1 and 2 are fin's `accounts` and `balances` tables, with the same `CREATE TABLE`
statements its Rails migrations wrote, read off `fin.sqlite3`:

- `accounts`: `id`, `owner`, `bank`, `name`, `reference`, `currency`
- `balances`: `id`, `account_id` (not null), `date` (not null), `description`, `cash_flow`
  (decimal(10,2), not null), `balance` (decimal(10,2), not null); one row per account and date

Migration 3 renames `accounts.bank` to `institution`: the firm that holds an account is rarely a
bank (Vanguard, an insurer, a pension fund). From there the schema is maison's own, no longer
fin's. Migration 4 renames the description "Interest" to "Statement": such a balance only says what
the account was worth, read off a statement, and the change in it is not interest alone.

A fin database (`user_version` 0 with a `balances` table) is marked as being at `FIN_VERSION`, so
migrations 1 and 2 never run on it, only those after, and a copy of `fin.sqlite3` opens. Its Rails tables
(`schema_migrations`, `ar_internal_metadata`) and its old `aaa_*` tables are left alone.

## Themes

`t` opens tui-kit's theme picker and the choice is saved to `~/.config/maison/config.yaml`; there
is no Settings panel. Anything drawn with Rich instead of TCSS must take its colors from
`BaseApp.palette`, and its view repaints it in a `set_colors` method, which `MaisonApp.apply_theme`
calls on every view that has one.

## Versions

The version comes from git tags via setuptools-scm. Tags have no `v` prefix. Release by
tagging: `git tag 0.1.0`.

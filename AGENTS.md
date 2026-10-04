# maison

TUI with home tools, one tab each: `maison money` (the default) says which tab it opens on.
Money keeps track of investment accounts, a port of the fin Ruby gem (`~/jmoniatte/fin`,
the reference for the old behavior).

It is built on [tui-kit](https://github.com/jmoniatte/tui-kit), shared with outils, flotte
and yafyaf-tui: the themes and the picker (`t`), the messages, Help (`?`), the
dialogs, the startup check and the buttons' look (the `tinted` class, with `-green` or `-red`)
all come from there. Put what every app would use in tui-kit, not here; see its AGENTS.md. It is
laid out like outils: no border around the screen and no title bar (tui-kit's `AppHeader`): the
tabs are the first row, and every message, errors included, goes to the footer, in Help's place
(see Modes).

## Rules

- Do not git commit unless asked
- Specs come before code: describe a feature here before building it
- Keep the shortcuts few: the ones on the Help panel are the whole set
- The help screen lists every binding that has a description and a `group`
  (`tui_kit.shortcuts.ACTIONS` or `GENERAL`) in `MaisonApp.BINDINGS` and in the tab's view's
  `BINDINGS` (or its `HELP_BINDINGS`); document a new key there
- Never hardcode a color in a `.tcss` file

## Run

```bash
maison            # Money
maison money
```

It refuses to start unless stdin and stdout are a terminal (tui-kit's `start`).

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
    __main__.py         # The command line: which tab to open on
    config.py           # Optional ~/.config/maison/config.yaml (theme, through tui_kit.config; database_path)
    database.py         # The SQLite database: opening it and its migrations; no Textual
    money.py            # Accounts, balances, periods and returns, as fin worked them out, and their writes; no Textual
    cells.py            # right and signed: the Rich text of numbers, for the tables and the form; no Textual
    click_only.py       # click_only: a widget a click does not give focus to
    screens/
      help_screen.py    # MaisonHelpScreen: tui-kit's Help, the app's keys and the tab's own
      transaction_screen.py  # TransactionScreen: the form for a new balance
    widgets/
      money_view.py     # MoneyView, the Money tab: loads the accounts, switches between its two pages
      dashboard.py      # Dashboard, the first page: an AccountsTable per owner
      account_page.py   # AccountPage: one account's details, then its transactions, balance chart and returns
      balance_chart.py  # BalanceChart: the balance over time as a braille line
      money_table.py    # MoneyTable, the table both pages use, and SectionTitle
    styles/maison.tcss  # maison's own styles, joined after tui-kit's (app.STYLE_FILES)
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

## Money

`MoneyView` holds two pages in a `ContentSwitcher` (`#money-pages`): the `Dashboard`, which lists
the accounts, and the `AccountPage`, for one account. It reads the accounts from the database each
time the tab shows and on a theme change, since the colors are baked into the cells
(`MoneyView.load`, async since the dashboard mounts its tables, so `tab_shown` runs it with
`call_next`), and draws both pages again, keeping the account on show and the one the dashboard's
cursor was on (`Dashboard.current`). When the database could not open, the pages are hidden and
the footer says why. The pages tell `MoneyView` what happened by message, `Dashboard.Opened` and
`AccountPage.Closed`, and know nothing of each other.

The dashboard opens first. Enter or a click opens an account; Escape, Backspace, the Back button
or "Accounts" in its breadcrumbs go back, the dashboard's cursor on the account left.

Both pages start with breadcrumbs, as flotte's: on the dashboard "Accounts", in blue; on an account's
page "Accounts > Brokerage", "Accounts" in
blue, underlined under the pointer, a link back to the dashboard, `>` grey, then the account's name
in yellow, with the New Transaction and Back buttons at the right of the same row.
`MoneyView.action_back` raises `SkipAction` on the dashboard, so Escape there quits, as on every
tab. Help lists Enter (the dashboard's, through `HELP_BINDINGS`, "Open the account or transaction"),
`← →` and Escape. Tried and dropped: a
left-hand list of pages, as vertical tabs, and the dashboard's labels shown once, pinned at the
top.

### Tables

Both pages draw their rows in `MoneyTable`s (`money_table.py`). `MoneyTable.fill` gives each
column the width of its widest cell (or label) plus two, and lays every cell out to that exact
width with a space each side (`padded`; Rich would drop the trailing space of a right-aligned
cell), so the table has no cell padding (`cell_padding=0`) and a line of dashes runs across it
with no gaps (`table_width` says how wide `fill` makes a table). `fill` takes the rows to pick and
a footer, such as totals, which goes under that line of dashes; the cursor never lands on the
dashes or the footer (`MoneyTable.pickable_rows`, `validate_cursor_coordinate`), and a click
there changes nothing. A click on a row picks it, as Enter does: `MoneyTable` handles the click
itself, since `DataTable` picks only on a second click in the same cell. `right` and `signed` (`cells.py`, shared with the form) make the
cells of numbers: aligned right, and for `signed` green above 0 and red below. Over each table, a
`SectionTitle` (`── Joint ────`) on the dashboard, in yellow, as wide as the table, sets it apart,
so there are no dashes under its labels; the account page's tables, under their tabs, have a line
of dashes under the labels (`dashes_under_labels`, which makes the header two rows).

One row at most is shaded: the cursor follows the pointer, in place of `DataTable`'s own hover
shade, so the mouse and the keys move the same grey row (`MoneyTable._on_mouse_move`, which also
gives its table focus; Textual runs the base class's handler too unless `prevent_default`). The
pointer moves it only over a row it can be on (`MoneyTable.pickable_rows`); over the labels, the
dashes and the totals nothing changes. Only the table with focus shades its cursor's row (`:focus`
in the stylesheet). Colors never change under the cursor: `cursor_foreground_priority="renderable"`
makes a cell's own color (a green or red return, the blue "Total") win over its. When the table
shows its scrollbar, the shade stops two columns short of it (`MoneyTable.render_line`,
`SCROLLBAR_GAP`, as outils' Wi-Fi list does).

### Dashboard

fin's `fin accounts`, split by owner (`dashboard.py`). The `Dashboard` is the breadcrumbs' "Accounts"
over `#accounts-scroll`, a `VerticalScroll` with an `AccountsTable` per owner, under a yellow line with the owner's name across the table's width
(`── Joint ─────`), a blank row before the next owner: joint first, then the others by name
(Claire, then Elliot), then accounts with no owner, under "No owner" (`money.by_owner`; owners
compare in lower case). Each table has its labels, with no dashes under them (the owner's line
sets the table apart), then a row per account: Institution, Account, Balance (the latest), Yr Avg, the return per year
over its life (`Account.yearly_return`), first since it compares accounts best, then the return for each of the 5 latest years that have a balance, the latest first (fin read the
years from its config), and over the account's life. Then, as the table's footer, a Total row per currency
for that owner, "Total" in blue: fin had one total, adding USD and EUR together, which is wrong.
Returns are green above 0, red below; fin dropped the minus sign and relied on the color, here the
sign shows. Amounts have no decimals, rates one. A balance or total ends with its currency's symbol,
one space after it, where fin wrote the code (`700,307 $`, `34,141 €`; `money.money`, `SYMBOLS`:
dollar, euro and pound); right-aligned, the symbols line up. A currency with no symbol keeps its
code (`12 CHF`), which would push its amount out of line. Tried and dropped: the symbol before the
amount (`$700,307`), and in a column of its own (two spaces after the amount). The tables share their columns' widths, so they
line up, and are built again on each `Dashboard.show` (removed, then mounted).

The first table has focus when the dashboard opens. `↑` `↓` move over the accounts, past the last
account of a table into the next one and back (`AccountsTable.Leave`), never onto the totals. Each table is as tall as its labels and rows (`AccountsTable.on_mount` sets the
height, and the stylesheet lifts `DataTable`'s `max-height`), so only the dashboard scrolls: as
the keys move the cursor, `AccountsTable.reveal` scrolls it to the cursor's row, with the owner's
line and the labels over the first account and the totals under the last. The pointer never
scrolls it.

### An account's page

`AccountPage`. Under the breadcrumbs, a header: on the left the account's details, one per line, the labels grey and
padded so the colons line up (`Institution`, `Account Name`, `Account Number` (the `reference`),
`Account Owner`; a dash when empty), then by them, the same way, `Balance` with the currency's
symbol after it (`money.money`). The blue New Transaction button, at the right of the breadcrumbs,
opens the form for a new balance (see New and changed transactions). A Refresh button was tried
and dropped: saving reloads the page. Under
Balance, `Life Return`, the account's return over its life, and `Yr Avg`, that return as a
rate per year, green or red.

Under a blank row, three tabs (`#account-tabs`, `TABS`), each as tall as the rest of the page:
Transactions, Balances and Returns. An account opens on Transactions (`MoneyView` calls
`AccountPage.show`, which takes the tab, then `focus_tab` once the page shows); saving a transaction
keeps the tab on show. `←` `→` show the tab before or after, going
round from the last to the first (`AccountPage.action_switch_tab`, `priority` bindings, so they run
before the tables' own left and right; Help lists them as one line), as does a click on a tab. The
tabs cannot take focus: what the tab holds has it, its only child (the chart `can_focus` for that),
so the keys stay on the page; a hidden widget must never keep focus, since `TabbedContent` would switch to its tab.
`AccountPage._tab_activated` moves focus after a click, and only while focus is on the page, since
the tabs say they are activated when mounted too, while the dashboard shows. A chart over the
transactions, on one page, was tried and dropped: neither had the height it needed.

Transactions is one `MoneyTable`, so `↑` `↓` move over it. It joins fin's `fin balances` and `fin
periods`: one row per balance, the latest first (fin showed the oldest first), with Date,
Description, Cash flow, Gain (the change in balance less the cash flow: what the money earned or
lost, interest, dividends and prices alike), Balance and Return (the gain over the balance before
plus the cash flow). fin's year separators are not drawn.

Returns is a `MoneyTable` with a row per year, the latest first, from the first balance's year to
the last's (`Account.years`): Year, Start balance, Cash flow, Gain, End balance and Return.
The amounts add up the periods that end in the year, so a year with no balance keeps the one
before; the return is `return_rate(year)`, the dashboard's, so the two always match, and is empty
where fin's rule finds no period (Retraite LaCie, with one balance a year). Its footer: `Yr Avg`, the
return per year, only in the Return column, then `Life`, the account's whole life (`Account.life`): no start balance, every cash flow, the gain, the
latest balance and the return over its life.

### Balance chart

`BalanceChart`, the Balances tab, draws the balances as a line in braille characters, each two
dots wide and four tall, in blue, across the tab's width and height: time evenly across, from the
first balance to the last, and the balance up, from the lowest at the bottom to the highest at the
top, straight between two balances (`plot`, `value_at`, no Textual). A steep stretch is joined dot
by dot, so the line never breaks. Around it, in grey, two axes: on the left `│`, with a `┤` tick
on the top row, the bottom one and every quarter between, and that row's value before it; at the
bottom `└───`, with a `┬` tick where each new year begins and the year's number centered under it,
left out when it would run into the one before or past an edge, its tick kept; with no new year
in the span, the first year's number at the left (`x_axis`). It is drawn again to fit whenever its size changes (`render`),
and says "Not enough balances for a chart" with fewer than two. A second, grey line for the money
put in was tried and dropped. No chart library: Textual's `Sparkline` has no axes, and a plotting
package would be a dependency.

### New and changed transactions

New Transaction (fin's `fin record`), or Enter or a click on a row of Transactions, opens
`TransactionScreen`, titled with the account's full name ("Brokerage @ Vanguard",
`Account.full_name`), a modal form over the page in flotte's style: tui-kit's box
(`modal_forms.tcss`), grey labels, and fields with no box, only a line under them, blue when
focused. Its fields: Date, Cash flow (put in, or taken out below 0), Description (empty means
Statement, the placeholder: a balance read off a statement) and Balance ("New balance"), which has focus. New, they hold today and
0; for a row, that balance, the amounts as one would type them (`money.typed`: commas, cents only
when there are some). Amounts may be typed with commas, spaces and a currency symbol
(`money.parse_amount`). A line under the fields gives the gain and return the balance makes
over the one before its date, leaving out the one being changed (`Account.balance_on`), green or
red, as the fields are typed. Save, or Enter in any field, checks the fields and says in red under
them what is wrong: a date not like 2026-10-03, a cash flow or balance that is not a number, a
missing balance, or a cash flow with no description. The gain line and the error line show
only when they have something to say, so an empty one leaves no blank row over the buttons. Cancel
or Escape closes it and records nothing. Cancel is red, Save green (tui-kit's `tinted` buttons).

A changed balance also has a red Delete button, on the left, away from Save. It asks first with
tui-kit's `ConfirmDialog` ("Delete the balance of 2025-11-30?", the description and balance under
it), whose Keep has focus, so a reflexive Enter keeps it.

The screen returns the `Balance` to save (its id 0 when new) or a `Deletion`; `AccountPage` posts
`AccountPage.Changed`, and `MoneyView`, which alone writes to the database, records it
(`money.add_balance`, `update_balance` or `delete_balance`), reads the accounts again and says
"Transaction added", "saved" or "deleted for <account>" in the footer. The transactions' cursor
stays on its row. Nothing else needs updating: periods, returns and the chart are worked out from
the balances, in date order, each time they are read. A balance can go on any date, before others
too; changing one changes its own row's gain and return and the next one's, and deleting one
joins the periods either side of it.

### Returns

`money.py` does fin's maths, checked against `fin accounts` on the real data (every rate and
balance the same). Each balance closes a period that starts at the balance before (the first
starts at 0 on its own date). A period's return is `(end - start - cash_flow) / (start +
cash_flow)`. A return over several periods is time-weighted: the periods' `1 + return`
multiplied, less 1. A year takes the periods that start and end within it, with 5 days of slack at
each end (`YEAR_SLACK`); none means no return, an empty cell. A period with nothing to earn on
(`start + cash_flow` is 0) has no return and is left out of the product, where fin would have
divided by zero.

The return per year (`Account.yearly_return`, not in fin) is the return over the account's life
as a steady yearly rate: `(1 + life) ** (365.25 / days) - 1`, the days from its first balance to
its latest (21% over two years is 10% a year). Not an average of the yearly returns, which would
weigh a loss and a gain alike (-17% then +17% is not 0%) and count a part year as a whole one. Under
a year of balances it is empty: a few months made into a year mislead. Amounts are floats, as SQLite stores them.

### Not built yet

Editing and deleting a balance, and adding and editing accounts.

## Themes

`t` opens tui-kit's theme picker and the choice is saved to `~/.config/maison/config.yaml`; there
is no Settings panel. Anything drawn with Rich instead of TCSS must take its colors from
`BaseApp.palette`, and its view repaints it in a `set_colors` method, which `MaisonApp.apply_theme`
calls on every view that has one.

## Versions

The version comes from git tags via setuptools-scm. Tags have no `v` prefix. Release by
tagging: `git tag 0.1.0`.

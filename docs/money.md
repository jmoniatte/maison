# Money

`MoneyView` holds two pages in a `ContentSwitcher` (`#money-pages`): the `Dashboard`, which lists
the accounts, and the `AccountPage`, for one account. It reads the accounts from the database each
time the tab shows and on a theme change, since the colors are baked into the cells
(`MoneyView.load`, async since the dashboard mounts its tables, so `tab_shown` runs it with
`call_next`), and draws both pages again, keeping the account on show and the one the dashboard's
cursor was on (`Dashboard.current`). When the database could not open, the pages are hidden and
the footer says why. The pages tell `MoneyView` what happened by message, `Dashboard.Opened` and
`AccountPage.Closed`, and know nothing of each other.

The dashboard opens first. Enter or a click opens an account; Escape, Backspace or "Accounts" in its
breadcrumbs go back, the dashboard's cursor on the account left.

Both pages start with breadcrumbs, as flotte's: on the dashboard "Accounts", in blue; on an account's
page "Accounts > Brokerage", "Accounts" in
blue, underlined under the pointer, a link back to the dashboard, `>` grey, then the account's name
in yellow, with the New Transaction button at the right of the same row. A Back button was tried
and dropped: the breadcrumbs do its job.
`MoneyView.action_back` raises `SkipAction` on the dashboard, so Escape there quits, as on every
tab. Help lists Enter (the dashboard's, through `HELP_BINDINGS`, "Open the account or transaction"),
`← →` and Escape. Tried and dropped: a
left-hand list of pages, as vertical tabs, and the dashboard's labels shown once, pinned at the
top.

## Tables

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

## Dashboard

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

## An account's page

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

## Balance chart

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

## New and changed transactions

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

## Returns

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

## Not built yet

Adding and editing accounts.

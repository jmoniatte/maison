"""The Money tab's page for one account: its details, then its transactions, the latest first."""

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static, TabbedContent, TabPane, Tabs
from tui_kit.shortcuts import GENERAL

from ..click_only import click_only
from ..cells import right, signed
from ..money import Account, Balance, Year, amount, money, percent
from ..screens import Deletion, TransactionScreen
from .balance_chart import BalanceChart
from .money_table import MoneyTable

# The labels' width in the header, so the colons line up
LABEL_WIDTH = len("Account Number")
# The tabs under the header, in order, the first one on show when an account opens
TRANSACTIONS = "transactions"
BALANCES = "balances"
RETURNS = "returns"
TABS = (TRANSACTIONS, BALANCES, RETURNS)


class AccountPage(Vertical):
    """The breadcrumbs, "Accounts > Brokerage", with the New Transaction button at the right; a
    header with the account's details on the left and its balance by them; under it three tabs: Transactions, fin's balances and periods in one table,
    Balances, a chart of the balance over time, and Returns, a row per year."""

    BINDINGS = [
        # Before the tables' own left and right, which would scroll them sideways
        Binding("left", "switch_tab(-1)", priority=True),
        Binding("right", "switch_tab(1)", "Previous / next tab", key_display="← →", group=GENERAL, priority=True),
    ]

    class Closed(Message):
        """ "Accounts" in the breadcrumbs was clicked."""

    class Changed(Message):
        """A balance of the account was entered, changed or deleted, to record: change is the balance to
        save (its id 0 when new) or a Deletion."""

        def __init__(self, account: Account, change: Balance | Deletion) -> None:
            super().__init__()
            self.account = account
            self.change = change

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # The account on show, and its balances as the transactions list them
        self.account: Account | None = None
        self.transactions: list[Balance] = []

    def compose(self) -> ComposeResult:
        # As flotte's: "Accounts", which goes back, then the account's name; the buttons at the right
        with Horizontal(id="breadcrumbs"):
            yield Static("Accounts", id="breadcrumb-accounts")
            yield Static(">", id="breadcrumb-separator")
            yield Static("", id="breadcrumb-account", classes="breadcrumb-current", markup=False)
            yield Static(classes="spacer")
            yield click_only(Button("New Transaction", id="btn-new-transaction", classes="tinted"))
        with Horizontal(id="account-header"):
            yield Static("", id="account-details")
            yield Static("", id="account-balance")
        with TabbedContent(initial=TRANSACTIONS, id="account-tabs"):
            with TabPane("Transactions", id=TRANSACTIONS):
                yield MoneyTable(dashes_under_labels=True, id="account-table")
            with TabPane("Balances", id=BALANCES):
                # Takes focus while its tab shows, so the keys stay on this page
                chart = BalanceChart(id="balance-chart")
                chart.can_focus = True
                yield chart
            with TabPane("Returns", id=RETURNS):
                yield MoneyTable(dashes_under_labels=True, id="returns-table")

    def on_mount(self) -> None:
        # What each tab holds keeps focus; the tabs switch by click or with the arrows
        self.query_one(Tabs).can_focus = False

    def show(self, account: Account, tab: str | None = None) -> None:
        """Draw account, on tab, one of TABS, or on the tab on show; drawn again, the same account keeps
        the transactions' cursor where it was. focus_tab gives focus once the page shows."""
        if tab:
            self.query_one(TabbedContent).active = tab
        table = self.query_one("#account-table", MoneyTable)
        row = table.cursor_row if self.account and self.account.id == account.id else 0
        self.account = account
        self.query_one("#breadcrumb-account", Static).update(account.name)
        # The transactions' balances, in the table's order
        self.transactions = list(reversed(account.balances))
        self.query_one("#account-details", Static).update(self._fields((
            ("Institution", account.institution),
            ("Account Name", account.name),
            ("Account Number", account.reference),
            ("Account Owner", account.owner.capitalize()),
        )))
        life = account.return_rate()
        self.query_one("#account-balance", Static).update(self._fields((
            ("Balance", money(account.balance, account.currency)),
            ("Life Return", signed(life, percent(life), self.app.palette)),
            ("Yr Avg", signed(account.yearly_return, percent(account.yearly_return), self.app.palette)),
        )))
        self.query_one(BalanceChart).show([(balance.date, balance.balance) for balance in account.balances])
        palette = self.app.palette
        labels = [Text("Date"), Text("Description")] + [right(label) for label in ("Cash flow", "Gain", "Balance", "Return")]
        table.fill(labels, [
            (
                period.end_date.isoformat(),
                balance.description,
                signed(period.cash_flow, amount(period.cash_flow), palette),
                signed(period.gain, amount(period.gain), palette),
                right(amount(period.end_balance)),
                signed(period.return_rate, percent(period.return_rate), palette),
            )
            for balance, period in reversed(list(zip(account.balances, account.periods)))
        ])
        table.move_cursor(row=row, animate=False)
        self._fill_returns(account)

    def _fill_returns(self, account: Account) -> None:
        """A row per year, the latest first, then under a line of dashes the return per year over the
        account's life, and its whole life."""
        palette = self.app.palette

        def row(year: Year) -> tuple:
            return (
                str(year.year) if year.year else "Life",
                right(amount(year.start_balance)) if year.year else "",
                signed(year.cash_flow, amount(year.cash_flow), palette),
                signed(year.gain, amount(year.gain), palette),
                right(amount(year.end_balance)),
                signed(year.return_rate, percent(year.return_rate), palette),
            )

        table = self.query_one("#returns-table", MoneyTable)
        labels = [Text("Year")] + [right(label) for label in ("Start balance", "Cash flow", "Gain", "End balance", "Return")]
        per_year = ("Yr Avg", "", "", "", "", signed(account.yearly_return, percent(account.yearly_return), palette))
        table.fill(labels, [row(year) for year in account.years], [per_year, row(account.life)])
        table.move_cursor(row=0, animate=False)

    def _fields(self, fields: tuple[tuple[str, str | Text], ...]) -> Text:
        """Each field on its line, "Institution   : Vanguard", the label grey; a dash for an empty value."""
        comment = self.app.palette["comment"]
        return Text("\n").join(Text.assemble((f"{label:<{LABEL_WIDTH}}: ", comment), value or "–") for label, value in fields)

    def focus_tab(self) -> None:
        """Give what the tab on show holds focus, so the keys go to it."""
        # Never a hidden widget: TabbedContent would switch to its tab
        self.query_one(TabbedContent).active_pane.children[0].focus()

    def action_switch_tab(self, step: int) -> None:
        """Show the tab step places along, round from the last to the first."""
        tabs = self.query_one(TabbedContent)
        tabs.active = TABS[(TABS.index(tabs.active) + step) % len(TABS)]
        self.focus_tab()

    @on(TabbedContent.TabActivated, "#account-tabs")
    def _tab_activated(self, event: TabbedContent.TabActivated) -> None:
        # Not the app's own tabs. A click on a tab leaves focus on the page, in the tab now hidden; this is
        # also sent when mounted, while the dashboard shows, which keeps its focus
        event.stop()
        if self.has_focus_within:
            self.focus_tab()

    @on(events.Click, "#breadcrumb-accounts")
    def _back(self, event: events.Click) -> None:
        event.stop()
        self.post_message(self.Closed())

    @on(Button.Pressed, "#btn-new-transaction")
    def _new_transaction(self, event: Button.Pressed) -> None:
        event.stop()
        self._open(None)

    @on(MoneyTable.RowSelected, "#account-table")
    def _transaction_selected(self, event: MoneyTable.RowSelected) -> None:
        event.stop()
        self._open(self.transactions[event.cursor_row])

    def _open(self, balance: Balance | None) -> None:
        """The form for balance, or for a new one."""
        self.app.push_screen(TransactionScreen(self.account, balance), self._record)

    def _record(self, change: Balance | Deletion | None) -> None:
        if change is not None:
            self.post_message(self.Changed(self.account, change))

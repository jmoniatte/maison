"""The Money tab's first page: every account, a table per owner."""

from rich.text import Text
from textual import events, on
from textual.binding import Binding
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.geometry import Region
from textual.message import Message
from textual.widgets import DataTable, Static
from tui_kit.shortcuts import ACTIONS

from ..cells import right, signed
from ..money import Account, by_owner, money, percent, return_years, same_account, totals
from .money_table import MoneyTable, SectionTitle, column_widths, table_width


class AccountsTable(MoneyTable):
    """One owner's accounts, then their totals. Moving past the first or last account goes on to the
    table before or after."""

    BINDINGS = [Binding("enter", "select_cursor", "Open the account or transaction", group=ACTIONS)]

    class Leave(Message):
        """The cursor went past the first account (step -1) or the last (step 1)."""

        def __init__(self, table: "AccountsTable", step: int) -> None:
            super().__init__()
            self.table = table
            self.step = step

    def __init__(self, accounts: list[Account], labels: list[Text], rows: list[tuple], totals: list[tuple], widths: list[int]) -> None:
        super().__init__()
        self.accounts = accounts
        self._content = (labels, rows, totals, widths)

    def on_mount(self) -> None:
        self.fill(*self._content)
        # As tall as its labels and rows: the dashboard scrolls, never the table
        self.styles.height = self.header_height + self.row_count

    @property
    def account(self) -> Account:
        """The account the cursor is on."""
        return self.accounts[self.cursor_row]

    def action_cursor_up(self) -> None:
        if self.cursor_row == 0:
            self.post_message(self.Leave(self, -1))
        else:
            super().action_cursor_up()
            self.reveal()

    def action_cursor_down(self) -> None:
        if self.cursor_row == self.pickable_rows - 1:
            self.post_message(self.Leave(self, 1))
        else:
            super().action_cursor_down()
            self.reveal()

    def reveal(self) -> None:
        """Scroll the dashboard to the cursor's row, with the owner's line and the labels over the first
        account and the totals under the last."""
        rows_top = self.virtual_region.y + self.header_height
        top = rows_top + self.cursor_row
        bottom = top + 1
        if self.cursor_row == 0:
            # The owner's line sits right over the table
            top = self.virtual_region.y - 1
        if self.cursor_row == self.pickable_rows - 1:
            bottom = rows_top + self.row_count
        self.parent.scroll_to_region(Region(0, top, 1, bottom - top), animate=False, immediate=True)


class Dashboard(Vertical):
    """fin's account list: "Accounts", the first step of the breadcrumbs, then a table per owner under a
    yellow line with their name, which scroll under it. The tables share their columns' widths, so they
    line up."""

    class Opened(Message):
        """An account was picked, to show on its own page."""

        def __init__(self, account: Account) -> None:
            super().__init__()
            self.account = account

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # The account the cursor is on, which it comes back to once the tables are drawn again
        self.current: Account | None = None

    def compose(self) -> ComposeResult:
        yield Static("Accounts", id="accounts-title")
        yield VerticalScroll(id="accounts-scroll")

    async def show(self, accounts: list[Account]) -> None:
        """Draw the tables again for accounts, the cursor back on the current account if still there."""
        self.current = same_account(accounts, self.current)
        years = return_years(accounts)
        labels = [Text("Institution"), Text("Account"), right("Balance"), right("Yr Avg")]
        labels += [right(str(year)) for year in years] + [right("Life")]
        groups = [(owner, owned, self._rows(owned, years), self._totals(owned, years)) for owner, owned in by_owner(accounts)]
        widths = column_widths(labels, [row for *_, rows, sums in groups for row in rows + sums])
        widgets = []
        for owner, owned, rows, sums in groups:
            widgets.append(SectionTitle(owner.capitalize() or "No owner", table_width(widths)))
            widgets.append(AccountsTable(owned, labels, rows, sums, widths))
        scroll = self.query_one("#accounts-scroll", VerticalScroll)
        await scroll.remove_children()
        await scroll.mount_all(widgets)

    def _rows(self, accounts: list[Account], years: list[int]) -> list[tuple]:
        """Each account's institution, name and balance, then its returns: per year, over years and its life."""
        rows = []
        for account in accounts:
            rates = [account.yearly_return] + [account.return_rate(year) for year in years] + [account.return_rate()]
            rows.append((
                account.institution,
                account.name,
                right(money(account.balance, account.currency)),
                *(signed(rate, percent(rate), self.app.palette) for rate in rates),
            ))
        return rows

    def _totals(self, accounts: list[Account], years: list[int]) -> list[tuple]:
        """A row per currency: the accounts' balances added up."""
        blanks = [""] * (len(years) + 2)
        return [
            (Text("Total", style=self.app.palette["blue"]), "", right(money(total, currency), "bold"), *blanks)
            for currency, total in totals(accounts).items()
        ]

    def focus_current(self) -> None:
        """Put the cursor on the current account, or the first one, and give its table focus."""
        tables = list(self.query(AccountsTable))
        account = self.current or (tables[0].accounts[0] if tables else None)
        for table in tables:
            if account in table.accounts:
                self.current = account
                table.move_cursor(row=table.accounts.index(account), animate=False)
                table.focus()
                # Once laid out: the tables may have just been mounted
                table.call_after_refresh(table.reveal)

    @on(DataTable.RowHighlighted, "AccountsTable")
    def _highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Every table says so once filled; only the one with focus has the current account
        if event.data_table.has_focus:
            self.current = event.data_table.account

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        # The pointer moves a table's cursor before the table has focus
        if isinstance(event.widget, AccountsTable):
            self.current = event.widget.account

    @on(DataTable.RowSelected, "AccountsTable")
    def _selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        self.current = event.data_table.account
        self.post_message(self.Opened(self.current))

    @on(AccountsTable.Leave)
    def _leave(self, event: AccountsTable.Leave) -> None:
        tables = list(self.query(AccountsTable))
        index = tables.index(event.table) + event.step
        if 0 <= index < len(tables):
            self.current = tables[index].accounts[0 if event.step > 0 else -1]
            self.focus_current()

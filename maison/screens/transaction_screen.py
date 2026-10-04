from datetime import date
from typing import NamedTuple

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static
from tui_kit.dialog import ConfirmDialog

from ..cells import signed
from ..money import Account, Balance, Period, amount, parse_amount, percent, typed

# What a balance with no cash flow and no description is: the balance read off a statement
STATEMENT = "Statement"


class Deletion(NamedTuple):
    """The balance to delete, as TransactionScreen returns it."""

    balance: Balance


class TransactionScreen(ModalScreen[Balance | Deletion | None]):
    """A balance for an account, new (fin's `fin record`) or one to change: its date (today), the cash flow
    put in or taken out (0), a description (Statement when there is no cash flow) and the new balance.
    Under the fields, the gain and return it makes, as the fields are typed. It returns the balance
    to save (with the changed one's id, 0 when new), a Deletion, or None."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, account: Account, balance: Balance | None = None) -> None:
        super().__init__()
        self.account = account
        # The balance to change, None for a new one
        self.balance = balance

    def compose(self) -> ComposeResult:
        balance = self.balance
        with Vertical():
            yield Static(self.account.full_name, id="dialog-title", markup=False)
            for label, field, value, placeholder in (
                ("Date", "date", (balance.date if balance else date.today()).isoformat(), "YYYY-MM-DD"),
                ("Cash flow", "cash-flow", typed(balance.cash_flow) if balance else "0", "Put in, or taken out below 0"),
                ("Description", "description", balance.description if balance else "", STATEMENT),
                ("Balance", "balance", typed(balance.balance) if balance else "", "New balance"),
            ):
                with Horizontal(classes="form-row"):
                    yield Static(label, classes="field-label")
                    yield Input(value, placeholder=placeholder, id=field)
            yield Static("", id="transaction-preview")
            yield Static("", id="transaction-error", markup=False)
            with Horizontal(id="dialog-buttons"):
                if balance:
                    # On the left, away from Save
                    yield Button("Delete", id="delete-btn", classes="tinted -red")
                    yield Static(classes="spacer")
                yield Button("Cancel", id="cancel-btn", classes="tinted -red")
                yield Button("Save", id="save-btn", classes="tinted -green")

    def on_mount(self) -> None:
        self.query_one("#balance", Input).focus()
        if self.balance:
            self._preview()

    def _value(self, field: str) -> str:
        return self.query_one(f"#{field}", Input).value.strip()

    def _read(self) -> Balance | str:
        """The balance the fields make, or what is wrong with them."""
        try:
            day = date.fromisoformat(self._value("date"))
        except ValueError:
            return "The date must be like 2026-10-03"
        cash_flow = parse_amount(self._value("cash-flow") or "0")
        if cash_flow is None:
            return "The cash flow must be a number"
        balance = parse_amount(self._value("balance"))
        if balance is None:
            return "Enter the new balance"
        description = self._value("description")
        if not description:
            if cash_flow:
                return "Enter a description, such as Deposit"
            description = STATEMENT
        return Balance(self.balance.id if self.balance else 0, day, description, cash_flow, balance)

    @on(Input.Changed)
    def _preview(self) -> None:
        """The gain and return the balance makes, once the fields make one."""
        read = self._read()
        preview = Text()
        if isinstance(read, Balance):
            before = self.account.balance_on(read.date, leaving_out=self.balance)
            period = Period(read.date, read.date, before, read.cash_flow, read.balance)
            palette = self.app.palette
            preview = Text.assemble(
                ("Gain ", palette["comment"]),
                signed(period.gain, amount(period.gain), palette),
                ("    Return ", palette["comment"]),
                signed(period.return_rate, percent(period.return_rate) or "–", palette),
            )
        self._show_line("#transaction-preview", preview)
        self._show_line("#transaction-error", "")

    @on(Input.Submitted)
    @on(Button.Pressed, "#save-btn")
    def _save(self) -> None:
        read = self._read()
        if isinstance(read, str):
            self._show_line("#transaction-error", read)
            return
        self.dismiss(read)

    def _show_line(self, selector: str, content: str | Text) -> None:
        # Hidden while empty, so it leaves no blank row over the buttons
        line = self.query_one(selector, Static)
        line.update(content)
        line.display = bool(content)

    @on(Button.Pressed, "#delete-btn")
    def _delete(self) -> None:
        balance = self.balance
        dialog = ConfirmDialog(
            f"Delete the balance of {balance.date.isoformat()}?",
            title="Delete transaction",
            confirm_label="Delete",
            cancel_label="Keep",
            detail=f"{balance.description}, {amount(balance.balance)}",
        )
        self.app.push_screen(dialog, self._confirmed)

    def _confirmed(self, confirmed: bool) -> None:
        # Not a lambda: Textual would await the dismiss it returns, which it refuses from this screen
        if confirmed:
            self.dismiss(Deletion(self.balance))

    @on(Button.Pressed, "#cancel-btn")
    def action_cancel(self) -> None:
        self.dismiss(None)

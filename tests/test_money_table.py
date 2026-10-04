import unittest

from rich.text import Text

from maison.cells import right, signed
from maison.widgets.money_table import column_widths, padded

PALETTE = {"green": "#00ff00", "red": "#ff0000"}


class MoneyTableTest(unittest.TestCase):
    def test_cells_are_laid_out_to_the_width_with_a_space_each_side(self) -> None:
        self.assertEqual([str(padded(cell, 9)) for cell in ("USD", right("1,234"), Text(""))], [" USD     ", "   1,234 ", "         "])
        # The cell's colors stay
        self.assertEqual(padded(Text("Total", style="blue"), 9).spans[0].style, "blue")

    def test_widths_come_from_the_labels_and_the_cells(self) -> None:
        self.assertEqual(column_widths([Text("Institution"), right("Balance")], [("Vanguard", right("12")), ("UBS", right("1,234,567"))]), [11, 9])

    def test_signed_numbers_are_green_above_zero_and_red_below(self) -> None:
        self.assertEqual([signed(value, "x", PALETTE).style for value in (1, -1, 0, None)], ["#00ff00", "#ff0000", "", ""])
        self.assertEqual(signed(1, "x", PALETTE).justify, "right")


if __name__ == "__main__":
    unittest.main()

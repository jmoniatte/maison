import unittest
from datetime import date

from maison.widgets.balance_chart import plot, value_at, x_axis

START = date(2024, 1, 1)


class BalanceChartTest(unittest.TestCase):
    def test_the_line_goes_from_the_lowest_point_at_the_bottom_to_the_highest_at_the_top(self) -> None:
        rising = plot([(START, 0), (date(2024, 1, 11), 100)], 2, 1)
        # Two cells, two columns of dots each: up a row of dots per column, each joined to the one before
        self.assertEqual(rising, ["⣠⠞"])
        self.assertEqual(plot([(START, 5), (date(2024, 1, 11), 5)], 1, 1), ["⠤"])
        self.assertEqual(plot([], 3, 2), ["   ", "   "])

    def test_values_between_points_are_on_a_straight_line(self) -> None:
        points = [(START, 100), (date(2024, 1, 11), 200), (date(2024, 1, 21), 0)]
        self.assertEqual([value_at(points, START, day) for day in (0, 5, 10, 15, 20, 30)], [100, 150, 200, 100, 0, 0])

    def test_the_axis_has_a_tick_where_each_year_begins_and_its_number_under_it(self) -> None:
        self.assertEqual(x_axis(date(2023, 7, 1), date(2025, 7, 1), 21), ("─────┬─────────┬─────", "   2024      2025    "))
        # A number that would run into the one before or past an edge is left out; its tick stays
        self.assertEqual(x_axis(date(2023, 7, 1), date(2025, 7, 1), 8), ("──┬──┬──", "2024    "))
        # With no new year in the span, the first year's number at the left and no tick
        self.assertEqual(x_axis(date(2024, 1, 1), date(2024, 12, 31), 10), ("──────────", "2024      "))

if __name__ == "__main__":
    unittest.main()

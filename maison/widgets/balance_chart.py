"""A line chart of an account's balance over time, drawn in braille dots."""

from datetime import date

from rich.text import Text
from textual.widget import Widget

from ..money import amount

Points = list[tuple[date, float]]
# The dots of a braille character, by their column (0 or 1) and row (0 to 3) in the cell
DOTS = ((0x01, 0x02, 0x04, 0x40), (0x08, 0x10, 0x20, 0x80))
BRAILLE = 0x2800


def plot(points: Points, width: int, height: int) -> list[str]:
    """The points as a line in a grid of width × height braille characters, two dots wide and four
    tall each: time across, evenly, and the value up, from the lowest point at the bottom to the
    highest at the top. Between two points the line goes straight."""
    if not points or width < 1 or height < 1:
        return [" " * width] * height
    columns, rows = width * 2, height * 4
    start, end = points[0][0], points[-1][0]
    span = (end - start).days
    low, high = min(value for _, value in points), max(value for _, value in points)
    cells = [[0] * width for _ in range(height)]
    previous = None
    for x in range(columns):
        day = x / (columns - 1) * span if columns > 1 else 0
        y = rows - 1 - round((value_at(points, start, day) - low) / (high - low) * (rows - 1)) if high > low else rows // 2
        # Every dot from the last column's height to this one's, so a steep stretch stays joined
        top, bottom = sorted((y, y if previous is None else previous))
        for dot in range(top, bottom + 1):
            cells[dot // 4][x // 2] |= DOTS[x % 2][dot % 4]
        previous = y
    return ["".join(chr(BRAILLE + cell) if cell else " " for cell in row) for row in cells]


def value_at(points: Points, start: date, day: float) -> float:
    """The value day days after start, straight between the points around it."""
    for (before, low), (after, high) in zip(points, points[1:]):
        days_before, days_after = (before - start).days, (after - start).days
        if day <= days_after:
            share = (day - days_before) / (days_after - days_before) if days_after > days_before else 1
            return low + (high - low) * share
    return points[-1][1]


def x_axis(start: date, end: date, width: int) -> tuple[str, str]:
    """Under a chart width characters wide from start to end: the axis, with a tick where each new year
    begins, and under it each year's number centered on its tick, unless it would run into the one
    before or past an edge. With no new year in the span, the first year's number at the left."""
    span = (end - start).days
    ticks = [
        (year, round((date(year, 1, 1) - start).days / span * (width - 1))) for year in range(start.year + 1, end.year + 1)
    ]
    axis, labels = ["─"] * width, [" "] * width
    free = 0
    for year, column in ticks:
        axis[column] = "┬"
        label = str(year)
        left = column - len(label) // 2
        if left >= free and left + len(label) <= width:
            labels[left:left + len(label)] = label
            free = left + len(label) + 1
    if not ticks:
        labels[:4] = str(start.year)[:width]
    return "".join(axis), "".join(labels)


class BalanceChart(Widget):
    """An account's balance over time: the line in blue, and in grey its axes, the value of every quarter
    of the way from the lowest balance to the highest on a tick of the left one, and the years on the
    bottom one. It fits the line to its size whenever it is drawn."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.points: Points = []

    def show(self, points: Points) -> None:
        self.points = points
        self.refresh()

    def render(self) -> Text:
        palette = self.app.palette
        # The last two rows are the axis and the years under it
        height = self.size.height - 2
        if len(self.points) < 2 or height < 1:
            return Text("Not enough balances for a chart", style=palette["comment"])
        values = [value for _, value in self.points]
        low, high = min(values), max(values)
        # A value on the top and bottom rows and every quarter between, each the value its row stands for
        labels = {
            row: amount(high - row / max(height - 1, 1) * (high - low))
            for row in sorted({round(quarter * (height - 1) / 4) for quarter in range(5)})
        }
        gutter = max(len(label) for label in labels.values()) + 1
        # The axis takes a column after the labels
        width = self.size.width - gutter - 1
        text = Text(no_wrap=True)
        for index, row in enumerate(plot(self.points, width, height)):
            label = labels.get(index)
            text.append(f"{label or '':>{gutter - 1}} {'┤' if label else '│'}", style=palette["comment"])
            text.append(row + "\n", style=palette["blue"])
        axis, years = x_axis(self.points[0][0], self.points[-1][0], width)
        text.append(f"{' ' * gutter}└{axis}\n{' ' * (gutter + 1)}{years}", style=palette["comment"])
        return text

# maison

Home tools in the terminal, one tab each.

The first tab, Todos, lists what there is to do, as a search: `is:open` (the default),
`is:closed`, or neither for all, and words that the name or note must have ("furnace"). Open
todos come first, the soonest first: overdue in red, due soon in yellow, and those for some day
last. **New Todo** (`n`) adds one; a todo can warn several times before its date (renew a
passport: 6 months before, then 5). `Enter` or a click opens a todo's page, in the list's place, with room for a note on many lines,
to change or delete it; `x` (or a click on its box) opens it to close the todo, with its outcome,
or to reopen it; `p` (or a click on its star) pins it; `f` goes round Open, Closed and All. `maison due` prints the todos due, and `maison due --email` emails each reminder once, from a
daily timer (see [docs/todos.md](docs/todos.md#email)).

The second tab, Money, keeps track of investment accounts (a port of fin). It opens on the dashboard: every account's balance and yearly
returns, and the totals per currency. `Enter` or a click opens an account: its details and return
over its life, then three tabs: Transactions, its balances, the latest first, with the gain
and return of each; Balances, a chart of the balance over time; and Returns, a row per year, then
the whole life. `←` and `→` switch. **New Transaction** opens a form for a
new balance: its date, the cash flow put in or taken out, a description and the balance after it,
with the gain and return it makes shown as you type. `Enter` or a click on a transaction opens it in the same form, to change it or delete it.
`Esc`, or **Accounts** at the top, goes back.

## Install

```bash
./install.sh
```

It installs `maison` as a [uv](https://docs.astral.sh/uv/) tool. It needs SSH access to GitHub,
where its shared UI library, [tui-kit](https://github.com/jmoniatte/tui-kit), lives.

## Use

```bash
maison            # opens on Todos
maison money
maison due        # prints the todos due; --email emails their reminders
```

Click a tab or press `Tab` to switch. `?` or the **Help** button at the bottom right shows the
shortcuts, `t` picks a theme, `y` copies the text selected with the mouse, and `q`, `Esc` or the
**Exit** button at the bottom left quits. Messages show at the bottom too, in Help's place until
they clear.

## Configuration

Nothing is required. Press `t` to browse the themes: each one applies as the cursor moves,
`enter` keeps it and `esc` restores the one you started on. The choice is written to
`~/.config/maison/config.yaml`, which you can also edit by hand:

```yaml
theme: one-light
database_path: ~/Dropbox/data/maison.sqlite3   # the default
```

The data is kept in that SQLite file, created on the first start. The default is in Dropbox, so
every computer sees the same data.

The default, `terminal`, reads the colours from the terminal itself. The other themes are
[base16 schemes](https://github.com/tinted-theming/schemes) named by their upstream slug.

`maison due --email` needs an `email` section; with Fastmail, make an app password for it:

```yaml
email:
  to: me@fastmail.com
  from: me@fastmail.com
  password: an app password
```

## Development

```bash
uv run maison
uv run python -m unittest discover -s tests
uv run ruff check .
```

Releases are git tags without a `v` prefix (`0.1.0`); the version is derived from them by
setuptools-scm.

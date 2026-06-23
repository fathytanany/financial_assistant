# Financial Assistant

Truthful multi-currency net-worth tracking, built from a budgeting app's daily backup.

Most budgeting apps tell you your balance. They **don't** tell you *why* it changed — how
much was new savings, how much was your home currency weakening, and how much was gold or
other assets moving. This project answers that, by ingesting the daily SQLite backup from the
[Budget Flow](https://apps.apple.com/us/app/budget-flow-expense-tracker/id1640091876) iOS app, enriching it with daily FX and
gold rates (and reusing the exact rates already embedded in your own transactions), and
decomposing every day's change into **contributions vs. unrealized FX vs. unrealized gold**.

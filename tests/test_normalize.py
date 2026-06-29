from networth.normalize import normalize


def test_balances_and_net_worth(fixture_backup):
    norm = normalize(fixture_backup)
    bal = norm.balances.set_index("name")

    assert bal.loc["Cash", "balance"] == 100000 + 500 - 200 - 5000 - 40000 + 1000  # 56,300
    assert bal.loc["Dollar", "balance"] == 200
    assert round(bal.loc["Gold", "balance"], 6) == 1.2

    assert bal.loc["Dollar", "value_egp"] == 200 * 55      # 11,000
    assert bal.loc["Gold", "value_egp"] == 1.2 * 200000    # 240,000
    assert round(norm.net_worth_egp, 2) == 307300.0        # balances ignore the stats flag


def test_flow_type_classification(fixture_backup):
    entries = normalize(fixture_backup).entries
    counts = entries["flow_type"].value_counts().to_dict()
    assert counts["transfer"] == 4       # two contra-linked pairs
    assert counts["cashflow"] == 2       # real income/expense (add-to-stats on)
    assert counts["adjustment"] == 1     # booked gain (add-to-stats off)
    assert entries["is_transfer"].sum() == 4


def test_cross_currency_delta_uses_stored_rate(fixture_backup):
    entries = normalize(fixture_backup).entries.set_index("pk")
    assert entries.loc[12, "delta"] == 100      # 5000 EGP / 50 -> 100 USD
    assert entries.loc[14, "delta"] == 0.2      # 40000 EGP / 200000 -> 0.2 XAU


def test_future_dated_entries_excluded(fixture_backup):
    """A planned 2099 entry (pk 17, +99,999) must not inflate today's balance."""
    norm = normalize(fixture_backup)
    assert 17 not in set(norm.entries["pk"])
    assert norm.balances.set_index("name").loc["Cash", "balance"] == 56300  # unchanged


def test_opening_adjustment_corrects_initial_balance(fixture_backup):
    """A one-time opening adjustment is folded into the account's initial balance, so the whole
    balance shifts by exactly that amount with no other change."""
    base = normalize(fixture_backup).balances.set_index("name").loc["Cash", "balance"]
    adj = normalize(fixture_backup, opening_adjustments={"Cash": -1234.5})
    assert round(adj.balances.set_index("name").loc["Cash", "balance"], 2) == round(base - 1234.5, 2)

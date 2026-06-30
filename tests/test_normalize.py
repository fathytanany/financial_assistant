from networth.normalize import normalize


def test_balances_and_net_worth(fixture_backup):
    norm = normalize(fixture_backup)
    bal = norm.balances.set_index("name")

    # ... - 100x3 is the recurring rent (one group, three occurrences) -> 56,000
    assert bal.loc["Cash", "balance"] == 100000 + 500 - 200 - 5000 - 40000 + 1000 - 100 * 3
    assert bal.loc["Dollar", "balance"] == 200
    assert round(bal.loc["Gold", "balance"], 6) == 1.2

    assert bal.loc["Dollar", "value_egp"] == 200 * 55      # 11,000
    assert bal.loc["Gold", "value_egp"] == 1.2 * 200000    # 240,000
    assert round(norm.net_worth_egp, 2) == 307000.0        # balances ignore the stats flag


def test_recurring_group_counts_each_occurrence(fixture_backup):
    """A recurring entry is one group (pk 20) with several Transaction occurrences; each
    occurrence is its own ledger row, so the -100 rent hits the balance three times."""
    entries = normalize(fixture_backup).entries
    rent = entries[entries["amount"] == -100.0]
    assert len(rent) == 3                                   # three monthly occurrences
    assert sorted(rent["date"].dt.month) == [1, 2, 3]
    assert rent["delta"].sum() == -300.0


def test_flow_type_classification(fixture_backup):
    entries = normalize(fixture_backup).entries
    counts = entries["flow_type"].value_counts().to_dict()
    assert counts["transfer"] == 4       # two contra-linked pairs
    assert counts["cashflow"] == 5       # income + expense + 3 rent occurrences (add-to-stats on)
    assert counts["adjustment"] == 1     # booked gain (add-to-stats off)
    assert entries["is_transfer"].sum() == 4


def test_cross_currency_delta_uses_stored_rate(fixture_backup):
    entries = normalize(fixture_backup).entries.set_index("pk")
    assert entries.loc[112, "delta"] == 100      # 5000 EGP / 50 -> 100 USD
    assert entries.loc[114, "delta"] == 0.2      # 40000 EGP / 200000 -> 0.2 XAU


def test_future_dated_entries_excluded(fixture_backup):
    """A planned 2099 occurrence (pk 117, +99,999) must not inflate today's balance."""
    norm = normalize(fixture_backup)
    assert 117 not in set(norm.entries["pk"])
    assert norm.balances.set_index("name").loc["Cash", "balance"] == 56000  # unchanged

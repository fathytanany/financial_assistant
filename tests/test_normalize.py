from networth.normalize import normalize


def test_balances_and_net_worth(fixture_backup):
    norm = normalize(fixture_backup)
    bal = norm.balances.set_index("name")

    assert bal.loc["Cash", "balance"] == 100000 + 500 - 200 - 5000 - 40000  # 55,300
    assert bal.loc["Dollar", "balance"] == 200
    assert round(bal.loc["Gold", "balance"], 6) == 1.2

    assert bal.loc["Dollar", "value_egp"] == 200 * 55      # 11,000
    assert bal.loc["Gold", "value_egp"] == 1.2 * 200000    # 240,000
    assert round(norm.net_worth_egp, 2) == 306300.0


def test_transfer_classification(fixture_backup):
    entries = normalize(fixture_backup).entries
    assert entries["is_transfer"].sum() == 4          # two transfer pairs
    real = entries[~entries["is_transfer"]]
    assert set(real["kind"]) == {"income", "expense"}


def test_cross_currency_delta_uses_stored_rate(fixture_backup):
    entries = normalize(fixture_backup).entries.set_index("pk")
    assert entries.loc[12, "delta"] == 100      # 5000 EGP / 50 -> 100 USD
    assert entries.loc[14, "delta"] == 0.2      # 40000 EGP / 200000 -> 0.2 XAU

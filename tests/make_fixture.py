"""Generate a tiny synthetic Budget Flow backup for tests.

Mirrors the real Core Data shape (one wide ``ZITEM`` table). Entries are chosen so balances
and attribution have known, exact values, and exercise ``ZINCLUDEINSTATISTICS`` — the
"add to stats" flag that separates real cash flow (stats on) from booked gains/adjustments
(stats off, e.g. marking an investment gain):

    Cash (EGP) 56,300 | Dollar (USD) 200 @55 | Gold (XAU) 1.2 @200,000
    net worth                                  = 307,300 EGP
    contributions  (stats-on, non-transfer)    =     300
    realized_gain  (stats-off, non-transfer)   =   1,000
    unrealized_fx  (USD 50 -> 55 on 200 units) =   1,000

This is the only fake data in the repo. Run directly to (re)create the committed fixture:
    uv run python tests/make_fixture.py
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

CORE_DATA_EPOCH = 978307200
FIXTURE = Path(__file__).parent / "fixtures" / "sample.sqlite"


def _cd(date_str: str) -> float:
    """Calendar date -> Core Data seconds (noon UTC avoids tz date-shift)."""
    dt = datetime.fromisoformat(date_str).replace(hour=12, tzinfo=timezone.utc)
    return dt.timestamp() - CORE_DATA_EPOCH


# pk, Z_ENT, name, ccy, initial, rate, archived
ACCOUNTS = [
    (1, 10, "Cash", "EGP", 100000.0, 1.0, 0),
    (2, 10, "Dollar", "USD", 100.0, 55.0, 0),
    (3, 10, "Gold", "XAU", 1.0, 200000.0, 0),
]

# pk, Z_ENT, account_pk, amount, rate1, src, tgt, type1, contra, in_stats, date
GROUPS = [
    (10, 19, 1, 500.0, 1.0, "EGP", "EGP", 0, None, 1, "2025-01-01"),     # income (cash flow)
    (11, 19, 1, -200.0, 1.0, "EGP", "EGP", 1, None, 1, "2025-01-05"),    # expense (cash flow)
    (12, 19, 2, 5000.0, 50.0, "EGP", "USD", 0, 13, 0, "2025-01-10"),     # transfer leg (in)
    (13, 19, 1, -5000.0, 1.0, "EGP", "EGP", 1, 12, 0, "2025-01-10"),     # transfer leg (out)
    (16, 19, 1, 1000.0, 1.0, "EGP", "EGP", 0, None, 0, "2025-01-12"),    # booked gain (stats off)
    (14, 19, 3, 40000.0, 200000.0, "EGP", "XAU", 0, 15, 0, "2025-01-15"),  # transfer leg (in)
    (15, 19, 1, -40000.0, 1.0, "EGP", "EGP", 1, 14, 0, "2025-01-15"),    # transfer leg (out)
    (17, 19, 1, 99999.0, 1.0, "EGP", "EGP", 0, None, 1, "2099-01-01"),   # future/planned -> excluded
]


def build(path: Path = FIXTURE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    con.execute(
        """
        CREATE TABLE ZITEM (
            Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER,
            ZNAME VARCHAR, ZCURRENCYCODE VARCHAR,
            ZINITIALBALANCE FLOAT, ZEXCHANGERATE FLOAT, ZISARCHIVED INTEGER,
            ZACCOUNT1 INTEGER, ZAMOUNT1 FLOAT, ZEXCHANGERATE1 FLOAT,
            ZSOURCECURRENCYCODE VARCHAR, ZTARGETCURRENCYCODE VARCHAR,
            ZTYPE1 INTEGER, ZCONTRAENTRY INTEGER, ZINCLUDEINSTATISTICS INTEGER, ZDATE2 FLOAT
        )
        """
    )
    for pk, ent, name, ccy, init, rate, arch in ACCOUNTS:
        con.execute(
            "INSERT INTO ZITEM (Z_PK,Z_ENT,ZNAME,ZCURRENCYCODE,ZINITIALBALANCE,ZEXCHANGERATE,ZISARCHIVED)"
            " VALUES (?,?,?,?,?,?,?)",
            (pk, ent, name, ccy, init, rate, arch),
        )
    for pk, ent, acct, amt, rate, src, tgt, typ, contra, in_stats, date in GROUPS:
        con.execute(
            "INSERT INTO ZITEM (Z_PK,Z_ENT,ZACCOUNT1,ZAMOUNT1,ZEXCHANGERATE1,"
            "ZSOURCECURRENCYCODE,ZTARGETCURRENCYCODE,ZTYPE1,ZCONTRAENTRY,ZINCLUDEINSTATISTICS,ZDATE2)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (pk, ent, acct, amt, rate, src, tgt, typ, contra, in_stats, _cd(date)),
        )
    con.commit()
    con.close()
    return path


if __name__ == "__main__":
    print("Wrote", build())

"""Generate a tiny synthetic Budget Flow backup for tests.

Mirrors the real Core Data shape (one wide ``ZITEM`` table) with three accounts and a
handful of entries chosen so balances and attribution have known, exact values:

    Cash (EGP) 55,300 | Dollar (USD) 200 @55 | Gold (XAU) 1.2 @200,000
    net worth = 306,300 EGP   external_flow = 300   unrealized_fx = 1,000

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

# pk, Z_ENT, account_pk, amount, rate1, src, tgt, type1, contra, date
GROUPS = [
    (10, 19, 1, 500.0, 1.0, "EGP", "EGP", 0, None, "2025-01-01"),
    (11, 19, 1, -200.0, 1.0, "EGP", "EGP", 1, None, "2025-01-05"),
    (12, 19, 2, 5000.0, 50.0, "EGP", "USD", 0, 13, "2025-01-10"),
    (13, 19, 1, -5000.0, 1.0, "EGP", "EGP", 1, 12, "2025-01-10"),
    (14, 19, 3, 40000.0, 200000.0, "EGP", "XAU", 0, 15, "2025-01-15"),
    (15, 19, 1, -40000.0, 1.0, "EGP", "EGP", 1, 14, "2025-01-15"),
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
            ZTYPE1 INTEGER, ZCONTRAENTRY INTEGER, ZDATE2 FLOAT
        )
        """
    )
    for pk, ent, name, ccy, init, rate, arch in ACCOUNTS:
        con.execute(
            "INSERT INTO ZITEM (Z_PK,Z_ENT,ZNAME,ZCURRENCYCODE,ZINITIALBALANCE,ZEXCHANGERATE,ZISARCHIVED)"
            " VALUES (?,?,?,?,?,?,?)",
            (pk, ent, name, ccy, init, rate, arch),
        )
    for pk, ent, acct, amt, rate, src, tgt, typ, contra, date in GROUPS:
        con.execute(
            "INSERT INTO ZITEM (Z_PK,Z_ENT,ZACCOUNT1,ZAMOUNT1,ZEXCHANGERATE1,"
            "ZSOURCECURRENCYCODE,ZTARGETCURRENCYCODE,ZTYPE1,ZCONTRAENTRY,ZDATE2)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pk, ent, acct, amt, rate, src, tgt, typ, contra, _cd(date)),
        )
    con.commit()
    con.close()
    return path


if __name__ == "__main__":
    print("Wrote", build())

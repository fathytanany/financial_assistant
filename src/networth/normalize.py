"""Silver layer: decode the Budget Flow Core Data backup into clean tables.

The backup keeps everything in one wide table ``ZITEM`` discriminated by ``Z_ENT``.
We extract two entities — Account (10) and TransactionGroup (19, the real money entry) —
and apply the validated balance rule (see specs/data-model.md):

    delta_in_account_ccy = amount            if source_ccy == account_ccy
                         = amount / rate     otherwise   (amount is in source ccy)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config


def _connect(path: Path) -> sqlite3.Connection:
    # Read-only; we never write to the backup.
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def load_accounts(con: sqlite3.Connection) -> pd.DataFrame:
    q = f"""
        SELECT Z_PK              AS pk,
               ZNAME             AS name,
               ZCURRENCYCODE     AS currency,
               COALESCE(ZINITIALBALANCE, 0.0) AS initial_balance,
               ZEXCHANGERATE     AS rate_egp,
               COALESCE(ZISARCHIVED, 0) AS archived
        FROM ZITEM
        WHERE Z_ENT = {config.ENT_ACCOUNT}
    """
    df = pd.read_sql_query(q, con)
    # EGP accounts store NULL/1.0; default the base currency to 1.0.
    df["rate_egp"] = df["rate_egp"].fillna(1.0)
    return df


def load_entries(con: sqlite3.Connection) -> pd.DataFrame:
    q = f"""
        SELECT g.Z_PK                AS pk,
               g.ZACCOUNT1           AS account_pk,
               a.ZCURRENCYCODE       AS account_currency,
               COALESCE(g.ZAMOUNT1, 0.0) AS amount,
               g.ZEXCHANGERATE1      AS rate,
               g.ZSOURCECURRENCYCODE AS src,
               g.ZTARGETCURRENCYCODE AS tgt,
               g.ZTYPE1              AS type_code,
               g.ZCONTRAENTRY        AS contra_pk,
               COALESCE(g.ZINCLUDEINSTATISTICS, 1) AS in_stats,
               datetime(g.ZDATE2 + {config.CORE_DATA_EPOCH}, 'unixepoch') AS ts
        FROM ZITEM g
        JOIN ZITEM a ON a.Z_PK = g.ZACCOUNT1
        WHERE g.Z_ENT = {config.ENT_GROUP} AND g.ZACCOUNT1 IS NOT NULL
    """
    df = pd.read_sql_query(q, con)
    df["date"] = pd.to_datetime(df["ts"]).dt.normalize()
    df["is_transfer"] = df["contra_pk"].notna()
    df["in_stats"] = df["in_stats"].fillna(1).astype(int) == 1
    df["kind"] = df["type_code"].map({0: "income", 1: "expense"}).fillna("other")
    # Classify how an entry affects net worth (see specs/data-model.md):
    #   transfer   - internal move between own accounts (ZCONTRAENTRY set); net-zero.
    #   cashflow   - real income/expense ("add to stats" ON) -> a contribution.
    #   adjustment - booked gain/correction ("add to stats" OFF) -> not a contribution.
    df["flow_type"] = [
        "transfer" if t else ("cashflow" if s else "adjustment")
        for t, s in zip(df["is_transfer"], df["in_stats"])
    ]
    df["delta"] = [
        (amt / rate) if (s != ccy and rate and rate > 0) else amt
        for amt, rate, s, ccy in zip(df["amount"], df["rate"], df["src"], df["account_currency"])
    ]
    return df.drop(columns=["ts"])


def compute_balances(accounts: pd.DataFrame, entries: pd.DataFrame) -> pd.DataFrame:
    sums = entries.groupby("account_pk")["delta"].sum()
    out = accounts.copy()
    out["balance"] = out["pk"].map(sums).fillna(0.0) + out["initial_balance"]
    out["value_egp"] = out["balance"] * out["rate_egp"]
    return out


@dataclass
class Normalized:
    accounts: pd.DataFrame
    entries: pd.DataFrame
    balances: pd.DataFrame

    @property
    def net_worth_egp(self) -> float:
        return float(self.balances["value_egp"].sum())


def normalize(backup_path: Path, opening_adjustments: dict[str, float] | None = None) -> Normalized:
    con = _connect(backup_path)
    try:
        accounts = load_accounts(con)
        entries = load_entries(con)
    finally:
        con.close()

    # Drop planned/future-dated entries: Budget Flow doesn't count a transaction in a
    # balance until its date arrives, so neither do we (otherwise a scheduled expense
    # would understate cash today).
    entries = entries[entries["date"] <= pd.Timestamp.now().normalize()].reset_index(drop=True)

    # Opening-balance reconciliation. A few accounts were created in Budget Flow carrying a
    # charge from *before* tracking began that the app applies to the displayed balance but
    # never exports as a transaction (validated: credit cards + the main current account). The
    # result is a wrong ZINITIALBALANCE — a constant offset, identical to the cent across
    # backups while every transaction since reconstructs exactly. We correct it once at the
    # source so the rest of the pipeline needs no special-casing. See specs/data-model.md.
    if opening_adjustments:
        adj = accounts["name"].map(opening_adjustments).fillna(0.0)
        accounts["initial_balance"] = accounts["initial_balance"] + adj

    return Normalized(accounts, entries, compute_balances(accounts, entries))

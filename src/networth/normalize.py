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
    # One ledger row per Transaction *occurrence* (Z_ENT=18), pulling its money from the parent
    # TransactionGroup (Z_ENT=19). A recurring entry is a single group with many dated
    # occurrences, so summing groups under-counts it; summing occurrences is what the app does
    # and what its CSV export shows. The occurrence owns the date (ZDATE1); the group owns the
    # amount/account/rate. See specs/data-model.md.
    q = f"""
        SELECT t.Z_PK                AS pk,
               g.ZACCOUNT1           AS account_pk,
               a.ZCURRENCYCODE       AS account_currency,
               COALESCE(g.ZAMOUNT1, 0.0) AS amount,
               g.ZEXCHANGERATE1      AS rate,
               g.ZSOURCECURRENCYCODE AS src,
               g.ZTARGETCURRENCYCODE AS tgt,
               g.ZTYPE1              AS type_code,
               g.ZCONTRAENTRY        AS contra_pk,
               COALESCE(g.ZINCLUDEINSTATISTICS, 1) AS in_stats,
               datetime(COALESCE(t.ZDATE1, t.ZPLANNEDDATE) + {config.CORE_DATA_EPOCH}, 'unixepoch') AS ts
        FROM ZITEM t
        JOIN ZITEM g ON g.Z_PK = t.ZTRANSACTIONGROUP2 AND g.Z_ENT = {config.ENT_GROUP}
        JOIN ZITEM a ON a.Z_PK = g.ZACCOUNT1
        WHERE t.Z_ENT = {config.ENT_TXN}
          AND g.ZACCOUNT1 IS NOT NULL
          AND COALESCE(t.ZDATE1, t.ZPLANNEDDATE) IS NOT NULL
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


def normalize(backup_path: Path) -> Normalized:
    con = _connect(backup_path)
    try:
        accounts = load_accounts(con)
        entries = load_entries(con)
    finally:
        con.close()

    # Drop planned/future-dated occurrences: Budget Flow doesn't count a transaction in a
    # balance until its date arrives, so neither do we (otherwise a scheduled expense
    # would understate cash today).
    entries = entries[entries["date"] <= pd.Timestamp.now().normalize()].reset_index(drop=True)

    return Normalized(accounts, entries, compute_balances(accounts, entries))

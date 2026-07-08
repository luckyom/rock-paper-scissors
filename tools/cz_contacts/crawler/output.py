"""Build the deliverables: XLSX (3 sheets) + a CSV export."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .models import COLUMNS, Contact


def contacts_to_frame(contacts: Iterable[Contact]) -> pd.DataFrame:
    rows = [c.as_row() for c in contacts]
    df = pd.DataFrame(rows, columns=COLUMNS)
    return df


def _stats_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["category", "region", "rows", "priority_A", "with_email"])
    g = df.copy()
    g["with_email"] = g["email"].astype(bool)
    g["priority_A"] = g["priority"].eq("A")
    out = (
        g.groupby(["category", "region"], dropna=False)
        .agg(rows=("organization", "size"),
             priority_A=("priority_A", "sum"),
             with_email=("with_email", "sum"))
        .reset_index()
        .sort_values(["category", "rows"], ascending=[True, False])
    )
    return out


def _top50_frame(df: pd.DataFrame) -> pd.DataFrame:
    a = df[df["priority"] == "A"].copy()
    # unknown distances sort last
    a["_km"] = pd.to_numeric(a["km_from_Prague"], errors="coerce").fillna(10_000)
    a = a.sort_values("_km").drop(columns="_km").head(50)
    return a


def write_outputs(contacts: Iterable[Contact], out_dir: str | Path,
                  basename: str = "LuckySings_CZ_Contact_Database") -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = contacts_to_frame(contacts)

    xlsx_path = out_dir / f"{basename}.xlsx"
    csv_path = out_dir / f"{basename}.csv"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="ALL", index=False)
        _top50_frame(df).to_excel(xw, sheet_name="TOP 50", index=False)
        _stats_frame(df).to_excel(xw, sheet_name="STATS", index=False)
        _autosize(xw)

    return {
        "xlsx": str(xlsx_path),
        "csv": str(csv_path),
        "rows": len(df),
        "priority_A": int((df["priority"] == "A").sum()) if not df.empty else 0,
        "with_email": int(df["email"].astype(bool).sum()) if not df.empty else 0,
    }


def _autosize(writer) -> None:
    for ws in writer.book.worksheets:
        for col in ws.columns:
            width = 12
            letter = None
            for cell in col:
                letter = cell.column_letter
                val = str(cell.value) if cell.value is not None else ""
                width = max(width, min(len(val) + 2, 60))
            if letter:
                ws.column_dimensions[letter].width = width
        ws.freeze_panes = "A2"

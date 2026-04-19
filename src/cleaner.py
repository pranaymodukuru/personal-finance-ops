"""
Data cleaning pipeline for personal finance transactions.

Usage:
    python -m src.cleaner [--input PATH] [--output PATH] [--report-only]

Reads  output/raw/cumulative.csv  (or --input)
Writes output/processed/cleaned_cumulative.csv (or --output)
Prints a JSON cleaning report to stdout on the last line.
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.subcategory import assign_subcategory

RAW_CSV = Path("output/raw/cumulative.csv")
CLEANED_CSV = Path("output/processed/cleaned_cumulative.csv")

IDENTITY_COLS = ["date", "transaction_date", "receiver", "amount", "type", "bank", "account_type"]

TEXT_COLS = [
    "receiver", "reference", "description", "category", "type",
    "payment_method", "account_type", "space", "city", "bank", "currency_original",
]
ENUM_COLS = ["category", "type", "payment_method", "account_type"]

SPARSE_COLS = [
    "currency_original", "amount_original", "exchange_rate",
    "payment_method", "reference", "space", "city",
]

# (pattern, canonical_name)
_RECEIVER_NORMALIZATION: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^rewe\b.*", re.I), "REWE"),
    (re.compile(r"^netto\b.*", re.I), "Netto"),
    (re.compile(r"^aldi\s+s[uüe]+[ed]?\b.*", re.I), "Aldi Süd"),
    (re.compile(r"^penny\b.*", re.I), "Penny"),
    (re.compile(r"^kaufland\b.*", re.I), "Kaufland"),
    (re.compile(r"^edeka\b.*", re.I), "Edeka"),
    (re.compile(r"^lidl\b.*", re.I), "Lidl"),
    (re.compile(r"^billa\b.*", re.I), "Billa"),
    (re.compile(r"^(interspar|spar)\b.*", re.I), "Spar"),
    (re.compile(r"^spicelands\b.*", re.I), "Spicelands"),
    (re.compile(r"^dookan\.com$|^sp\s+dookan$", re.I), "Dookan"),
]

VALID_CATEGORIES = {
    "food", "transport", "utilities", "entertainment", "healthcare",
    "shopping", "income", "savings", "transfer", "fees", "other", "insurance", "learning", "travel",
}

# (pattern, field, from_category_filter, to_category)
# field: "receiver" | "description" | "both"
# from_category_filter: only apply if current category matches (None = apply to any)
_RECLASSIFY_RULES: list[tuple[re.Pattern, str, str | None, str]] = [
    (re.compile(r"\bhotel\b|hostel|bb hotels|guesthouse|guest\s?house", re.I), "receiver", None, "travel"),
    (re.compile(r"airbnb", re.I), "receiver", None, "travel"),
    (re.compile(r"thalia|hugendubel", re.I), "receiver", "entertainment", "shopping"),
    (re.compile(r"3wickets", re.I), "receiver", None, "shopping"),
    (re.compile(r"big academy", re.I), "receiver", None, "learning"),
    (re.compile(r"fahrschule punkt offenbach|fahrschule.*offenbach", re.I), "receiver", None, "learning"),
    (re.compile(r"\bh&m\b|\bh\.m\b|\bh\s?&\s?m\b", re.I), "receiver", None, "shopping"),
    (re.compile(r"volkswohl", re.I), "receiver", None, "savings"),
    (re.compile(r"urbane wohnwerte|wohnwerte.*ii|hamburg.*team.*urban", re.I), "receiver", None, "utilities"),
    (re.compile(r"\bdt\.?\s*net\b|d\.t\.net", re.I), "receiver", None, "utilities"),
    (re.compile(r"datapart", re.I), "receiver", None, "learning"),
    (re.compile(r"dm.drogerie|dm markt|dm-drogerie|\bdm\b.*drogerie|drogerie markt", re.I), "receiver", None, "shopping"),
    (re.compile(r"stuttgart cricket verein|allgemeiner turnverein.*frankonia"
                r"|atv.*1873.*frankonia", re.I), "receiver", None, "healthcare"),
]

# (pattern, field, expected_category, skip_if_current_in)
# skip_if_current_in: categories where the current assignment is plausibly correct — don't flag
_CATEGORY_SIGNALS: list[tuple[re.Pattern, str, str, set[str]]] = [
    (re.compile(r"\bhotel\b|hostel|bb hotels|guesthouse|guest\s?house", re.I), "receiver", "travel", {"travel"}),
    (re.compile(r"airbnb", re.I), "receiver", "travel", {"travel"}),
    (re.compile(r"thalia|hugendubel", re.I), "receiver", "shopping", {"shopping"}),
    (re.compile(r"rewe|netto|lidl|aldi|edeka|penny|kaufland|lebensmittel", re.I), "receiver", "food", {"food"}),
    (re.compile(r"deutsche bahn|db vertrieb|öbb|oebb|flixbus|lufthansa|ryanair|easyjet", re.I), "receiver", "transport", {"transport", "income", "fees"}),
    (re.compile(r"miete|rent payment|kauselmann", re.I), "receiver", "utilities", {"utilities", "income", "transfer"}),
    (re.compile(r"n26.*member|zahlungsabsicherung", re.I), "receiver", "fees", {"fees"}),
    (re.compile(r"salary|gehalt|tvarit", re.I), "description", "income", {"income", "transfer", "savings"}),
    (re.compile(r"scalable capital|etf.*sparplan|sparplan.*etf", re.I), "receiver", "savings", {"savings", "transfer", "fees"}),
    (re.compile(r"reimburs|erstattung", re.I), "description", "income", {"income", "transfer", "transport", "entertainment", "savings"}),
]

OUTPUT_COLS = [
    "date", "transaction_date", "receiver", "reference", "description",
    "amount", "currency_original", "amount_original", "exchange_rate",
    "type", "category", "payment_method", "account_type", "space", "city",
    "bank", "is_internal_transfer", "subcategory",
]


def clean(
    input_path: Path = RAW_CSV,
    output_path: Path = CLEANED_CSV,
    write: bool = True,
) -> dict:
    """Run the full cleaning pipeline and return the JSON report dict."""
    df = _load(input_path)
    df, dedup_report = _dedup(df)
    df = _normalize_text(df)
    df = _normalize_receivers(df)
    df, reclassify_report = _reclassify_categories(df)
    df = _empty_to_nan(df)
    df = _coerce_types(df)
    df, anomaly_report = _validate(df)
    df = _flag_internal_transfers(df)
    df = _assign_subcategories(df)
    df = df[OUTPUT_COLS]

    if write:
        _write(df, output_path)

    report = _build_report(df, input_path, output_path, dedup_report, reclassify_report, anomaly_report, write)
    print(json.dumps(report))
    return report


def _load(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(
            f"ERROR: {path} not found. Run /process-statements first to extract transactions.",
            file=sys.stderr,
        )
        sys.exit(1)
    return pd.read_csv(path)


def _dedup(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    before = len(df)
    df = df.drop_duplicates(subset=IDENTITY_COLS, keep="first").reset_index(drop=True)
    removed = before - len(df)
    return df, {"removed": removed, "kept": len(df)}


def _normalize_text(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in TEXT_COLS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    for col in ENUM_COLS:
        if col in df.columns:
            df[col] = df[col].str.lower()
    return df


def _normalize_receivers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for pattern, canonical in _RECEIVER_NORMALIZATION:
        mask = df["receiver"].str.match(pattern, na=False)
        df.loc[mask, "receiver"] = canonical
    return df


def _reclassify_categories(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    changes: list[dict] = []

    for pattern, field, from_cat, to_cat in _RECLASSIFY_RULES:
        if field == "both":
            text = df["receiver"].fillna("") + " " + df["description"].fillna("")
        else:
            text = df[field].fillna("")

        matches = pattern.search
        hit = text.apply(lambda t: bool(matches(t)))
        if from_cat is not None:
            hit = hit & (df["category"] == from_cat)

        rows = df.index[hit & (df["category"] != to_cat)]
        for idx in rows:
            changes.append({
                "idx": int(idx),
                "receiver": str(df.at[idx, "receiver"]),
                "description": str(df.at[idx, "description"]),
                "from": str(df.at[idx, "category"]),
                "to": to_cat,
            })
            df.at[idx, "category"] = to_cat

    return df, {"count": len(changes), "changes": changes}


def _detect_category_suspects(df: pd.DataFrame) -> list[dict]:
    suspects: list[dict] = []
    for pattern, field, expected_cat, skip_cats in _CATEGORY_SIGNALS:
        if field == "both":
            text = df["receiver"].fillna("") + " " + df["description"].fillna("")
        else:
            text = df[field].fillna("")

        matches = pattern.search
        hit = text.apply(lambda t: bool(matches(t)))
        flagged = df.index[hit & ~df["category"].isin(skip_cats)]
        for idx in flagged:
            suspects.append({
                "idx": int(idx),
                "receiver": str(df.at[idx, "receiver"]),
                "description": str(df.at[idx, "description"]),
                "current_category": str(df.at[idx, "category"]),
                "suggested_category": expected_cat,
            })

    seen: set[int] = set()
    deduped: list[dict] = []
    for s in suspects:
        if s["idx"] not in seen:
            seen.add(s["idx"])
            deduped.append(s)
    return deduped


def _empty_to_nan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    na_values = {"", "nan", "None", "NaN"}
    for col in SPARSE_COLS:
        if col in df.columns:
            df[col] = df[col].replace(list(na_values), np.nan)
    return df


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["date", "transaction_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ["amount", "amount_original", "exchange_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _validate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    def _rows(mask: pd.Series) -> list[dict]:
        return [
            {
                "idx": int(i),
                "date": str(df.at[i, "date"])[:10] if pd.notna(df.at[i, "date"]) else None,
                "receiver": str(df.at[i, "receiver"]),
                "amount": float(df.at[i, "amount"]) if pd.notna(df.at[i, "amount"]) else None,
                "type": str(df.at[i, "type"]),
                "category": str(df.at[i, "category"]),
            }
            for i in df.index[mask]
        ]

    today = pd.Timestamp.now(tz=None).normalize()

    sign_mismatch_debit = _rows((df["type"] == "debit") & (df["amount"] > 0))
    sign_mismatch_credit = _rows((df["type"] == "credit") & (df["amount"] < 0))
    zero_amount = _rows(df["amount"] == 0)
    unknown_category = _rows(~df["category"].isin(VALID_CATEGORIES))
    future_date = _rows(df["date"].notna() & (df["date"] > today))

    category_suspect = _detect_category_suspects(df)

    anomaly_report = {
        "sign_mismatch_debit": sign_mismatch_debit,
        "sign_mismatch_credit": sign_mismatch_credit,
        "zero_amount": zero_amount,
        "unknown_category": unknown_category,
        "future_date": future_date,
        "category_suspect": category_suspect,
        "total_anomalies": (
            len(sign_mismatch_debit)
            + len(sign_mismatch_credit)
            + len(zero_amount)
            + len(unknown_category)
            + len(future_date)
            + len(category_suspect)
        ),
    }
    return df, anomaly_report


def _flag_internal_transfers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_internal_transfer"] = (
        df["account_type"].isin(["savings"])
        | df["receiver"].str.startswith("N26 Space", na=False)
        | df["receiver"].str.contains(r"N26 Main Account|^Main Account$", na=False, case=False)
    )
    return df


def _assign_subcategories(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["subcategory"] = df.apply(assign_subcategory, axis=1)
    return df


def _write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _build_report(
    df: pd.DataFrame,
    input_path: Path,
    output_path: Path,
    dedup_report: dict,
    reclassify_report: dict,
    anomaly_report: dict,
    written: bool,
) -> dict:
    internal_count = int(df["is_internal_transfer"].sum()) if "is_internal_transfer" in df.columns else 0
    unclassified = int((df["subcategory"] == "unclassified").sum()) if "subcategory" in df.columns else 0
    unique_subs = int(df["subcategory"].nunique()) if "subcategory" in df.columns else 0

    date_min = str(df["date"].min())[:10] if "date" in df.columns else None
    date_max = str(df["date"].max())[:10] if "date" in df.columns else None

    return {
        "status": "ok" if anomaly_report["total_anomalies"] == 0 else "anomalies_found",
        "input_path": str(input_path),
        "output_path": str(output_path),
        "written": written,
        "reclassified": reclassify_report,
        "rows": {
            "raw": dedup_report["kept"] + dedup_report["removed"],
            "after_dedup": dedup_report["kept"],
            "duplicates_removed": dedup_report["removed"],
            "final": len(df),
        },
        "columns": list(df.columns),
        "is_internal_transfer": {
            "total": internal_count,
            "external": len(df) - internal_count,
        },
        "subcategory": {
            "unique": unique_subs,
            "unclassified": unclassified,
        },
        "anomalies": anomaly_report,
        "banks": df["bank"].value_counts().to_dict() if "bank" in df.columns else {},
        "date_range": {"min": date_min, "max": date_max},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean cumulative transaction CSV")
    parser.add_argument("--input", type=Path, default=RAW_CSV)
    parser.add_argument("--output", type=Path, default=CLEANED_CSV)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print cleaning report without writing output file",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    clean(input_path=args.input, output_path=args.output, write=not args.report_only)

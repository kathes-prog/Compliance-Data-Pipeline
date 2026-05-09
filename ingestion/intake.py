"""
intake.py — Parse uploaded Excel or CSV files into a normalized DataFrame.

Handles inconsistent column names by mapping known aliases to canonical names.
Returns a ParseResult with the DataFrame (or None) and any parse-level errors.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Canonical column name → list of accepted aliases (all lowercased, stripped)
# ---------------------------------------------------------------------------
COLUMN_ALIASES: dict[str, list[str]] = {
    "student_id": [
        "student_id", "studentid", "student id", "id", "student",
        "student_number", "student number", "pupil_id", "pupil id",
    ],
    "date": [
        "date", "attendance_date", "attendance date", "session_date",
        "session date", "class_date", "class date", "event_date",
    ],
    "present": [
        "present", "attended", "attendance", "status", "is_present",
        "is present", "was_present", "was present", "in_attendance",
    ],
    # Optional but mapped if found
    "program": ["program", "program_name", "program name", "course", "activity"],
    "school":  ["school", "school_name", "school name", "site", "location"],
}

# Reverse map: alias → canonical
_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical
    for canonical, aliases in COLUMN_ALIASES.items()
    for alias in aliases
}

REQUIRED_COLUMNS = {"student_id", "date", "present"}


@dataclass
class ParseResult:
    df: Optional[pd.DataFrame] = None
    errors: list[str] = field(default_factory=list)
    original_columns: list[str] = field(default_factory=list)
    mapped_columns: dict[str, str] = field(default_factory=dict)  # original → canonical

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0 and self.df is not None


def parse_file(filepath: str) -> ParseResult:
    """
    Read an Excel or CSV file and return a ParseResult.
    Column names are normalized to canonical names where possible.
    """
    result = ParseResult()
    ext = os.path.splitext(filepath)[1].lower()

    # -----------------------------------------------------------------------
    # 1. Read the raw file
    # -----------------------------------------------------------------------
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(filepath, dtype=str)
        elif ext == ".csv":
            df = pd.read_csv(filepath, dtype=str)
        else:
            result.errors.append(
                f"Unsupported file type '{ext}'. Please upload an Excel (.xlsx/.xls) or CSV file."
            )
            return result
    except Exception as exc:
        result.errors.append(f"Could not read file: {exc}")
        return result

    # -----------------------------------------------------------------------
    # 2. Drop fully-empty rows / columns
    # -----------------------------------------------------------------------
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    df.columns = df.columns.str.strip()
    result.original_columns = df.columns.tolist()

    # -----------------------------------------------------------------------
    # 3. Map column names to canonical equivalents
    # -----------------------------------------------------------------------
    rename_map: dict[str, str] = {}
    for col in df.columns:
        canonical = _ALIAS_TO_CANONICAL.get(col.lower().strip())
        if canonical and canonical not in rename_map.values():
            rename_map[col] = canonical

    df.rename(columns=rename_map, inplace=True)
    result.mapped_columns = rename_map

    # -----------------------------------------------------------------------
    # 4. Check required columns are present after mapping
    # -----------------------------------------------------------------------
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        friendly = {
            "student_id": "Student ID",
            "date":       "Date",
            "present":    "Present / Attended",
        }
        result.errors.append(
            "Missing required column(s): "
            + ", ".join(friendly.get(c, c) for c in sorted(missing))
            + ". Could not map them from the uploaded file's headers: "
            + ", ".join(result.original_columns or ["(none found)"])
        )
        return result

    # -----------------------------------------------------------------------
    # 5. Strip whitespace from all string values
    # -----------------------------------------------------------------------
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()

    # Reset index so row numbers are predictable downstream
    df.reset_index(drop=True, inplace=True)
    result.df = df
    return result

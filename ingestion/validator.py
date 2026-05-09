"""
validator.py — Validate a parsed attendance DataFrame.

Checks:
  - Required columns present (enforced by intake.py, re-verified here)
  - Date column parseable
  - Present column contains recognisable boolean-like values
  - No blank student_id or date values
  - Duplicate (student_id, date) pairs within the same upload

Returns a ValidationResult with structured errors (column-level and row-level)
plus summary stats.
"""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# Values treated as True / False for the "present" column
PRESENT_TRUE  = {"yes", "y", "true", "1", "present", "attended", "x"}
PRESENT_FALSE = {"no",  "n", "false", "0", "absent",  "not present", ""}


@dataclass
class RowError:
    row: int          # 1-based row number (header = row 1, first data row = row 2)
    column: str
    value: str
    message: str


@dataclass
class ValidationResult:
    valid: bool = True
    column_errors: list[str] = field(default_factory=list)
    row_errors: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    df: Optional[pd.DataFrame] = None   # coerced DataFrame if valid
    stats: dict = field(default_factory=dict)

    def add_column_error(self, msg: str):
        self.column_errors.append(msg)
        self.valid = False

    def add_row_error(self, row: int, column: str, value: str, msg: str):
        self.row_errors.append(RowError(row=row, column=column, value=str(value), message=msg))
        self.valid = False

    @property
    def error_count(self) -> int:
        return len(self.column_errors) + len(self.row_errors)


def validate(df: pd.DataFrame) -> ValidationResult:
    """
    Validate a DataFrame produced by intake.parse_file().
    Returns a ValidationResult; call .valid to check overall pass/fail.
    """
    result = ValidationResult()
    df = df.copy()

    # -----------------------------------------------------------------------
    # 1. Re-verify required columns
    # -----------------------------------------------------------------------
    required = {"student_id", "date", "present"}
    missing = required - set(df.columns)
    if missing:
        for col in sorted(missing):
            result.add_column_error(f"Required column '{col}' is missing.")
        return result   # can't proceed without required columns

    # -----------------------------------------------------------------------
    # 2. Blank student_id
    # -----------------------------------------------------------------------
    blank_id_mask = df["student_id"].isna() | (df["student_id"].str.strip() == "")
    for idx in df.index[blank_id_mask]:
        result.add_row_error(idx + 2, "student_id", "", "Student ID is blank.")

    # -----------------------------------------------------------------------
    # 3. Parse and validate the date column
    # -----------------------------------------------------------------------
    parsed_dates: list[Optional[pd.Timestamp]] = []
    for idx, raw in df["date"].items():
        if pd.isna(raw) or str(raw).strip() == "":
            result.add_row_error(idx + 2, "date", "", "Date is blank.")
            parsed_dates.append(None)
            continue
        try:
            parsed_dates.append(pd.to_datetime(str(raw).strip()))
        except (ValueError, TypeError):
            result.add_row_error(
                idx + 2, "date", str(raw),
                f"Cannot parse '{raw}' as a date. Expected formats: MM/DD/YYYY, YYYY-MM-DD, etc."
            )
            parsed_dates.append(None)

    df["date"] = parsed_dates

    # -----------------------------------------------------------------------
    # 4. Parse and validate the present column
    # -----------------------------------------------------------------------
    parsed_present: list[Optional[bool]] = []
    for idx, raw in df["present"].items():
        normalised = str(raw).strip().lower() if not pd.isna(raw) else ""
        if normalised in PRESENT_TRUE:
            parsed_present.append(True)
        elif normalised in PRESENT_FALSE:
            parsed_present.append(False)
        else:
            result.add_row_error(
                idx + 2, "present", str(raw),
                f"Unrecognised attendance value '{raw}'. "
                "Expected: Yes/No, True/False, 1/0, Present/Absent."
            )
            parsed_present.append(None)

    df["present"] = parsed_present

    # -----------------------------------------------------------------------
    # 5. Duplicate (student_id, date) pairs
    # -----------------------------------------------------------------------
    # Only check rows where both values parsed successfully
    checkable = df.dropna(subset=["student_id", "date"])
    checkable = checkable[checkable["student_id"].str.strip() != ""]
    dupes = checkable[checkable.duplicated(subset=["student_id", "date"], keep=False)]

    if not dupes.empty:
        # Group by the pair and report each group once
        groups = dupes.groupby(["student_id", "date"], dropna=False)
        for (sid, dt), group_df in groups:
            rows = [i + 2 for i in group_df.index.tolist()]
            result.add_row_error(
                rows[0], "student_id", str(sid),
                f"Duplicate entry: student '{sid}' on {str(dt)[:10]} "
                f"appears {len(rows)} times (rows {rows})."
            )

    # -----------------------------------------------------------------------
    # 6. Warn about unrecognised extra columns
    # -----------------------------------------------------------------------
    known = {"student_id", "date", "present", "program", "school", "category"}
    extra = set(df.columns) - known
    if extra:
        result.warnings.append(
            f"Unrecognised column(s) will be ignored: {', '.join(sorted(extra))}"
        )

    # -----------------------------------------------------------------------
    # 7. Summary stats
    # -----------------------------------------------------------------------
    result.stats = {
        "total_rows":    len(df),
        "error_rows":    len({e.row for e in result.row_errors}),
        "duplicate_rows": len(dupes),
        "blank_ids":     int(blank_id_mask.sum()),
    }

    if result.valid:
        result.df = df

    return result

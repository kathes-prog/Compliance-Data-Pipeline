# Netter Center Data Pipeline

A local desktop web app that replaces the manual workflow of cleaning attendance spreadsheets, reconciling CitiSpan compliance exports, and preparing Tableau-ready data. Built for the Netter Center for Community Partnerships at the University of Pennsylvania.

---

## What It Does

Schools and programs submit attendance data in inconsistent spreadsheet formats. CitiSpan compliance data is exported separately. Currently, staff reconcile all of this by hand before loading it into Tableau — a process that's slow, error-prone, and means dashboards are only as current as the last manual update.

This pipeline standardizes intake, automates cleaning and reconciliation, and outputs Tableau-ready CSVs automatically. Everything runs locally — no cloud hosting, no external dependencies, no cost.

---

## How to Run It

**Requirements:** Python 3.10+

**Mac / Linux:**
```bash
./run.sh
```

**Windows:**
```
run.bat
```

Both scripts will automatically create a virtual environment, install dependencies, and start the app at `http://localhost:5000`. No setup beyond that.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Backend | Python + Flask |
| Data processing | pandas + openpyxl |
| Database | SQLite |
| Frontend | Flask templates + plain HTML/CSS |
| Output | CSV (Tableau connects natively) |

Kept deliberately simple — no build step, no cloud infrastructure, no framework overhead. The entire app is a single SQLite file and a Python process.

## Wishlist

- **CitiSpan API integration** — currently requires a manual CSV export; direct API access would make reconciliation fully automatic
- **Tableau Hyper API output** — CSV works fine for now, but Hyper files load faster and support larger datasets in Tableau
- **Conflict resolution UI** — when a record can't be matched to CitiSpan, the current plan is to flag it; a proper UI for resolving those flags manually would be more useful than a raw list
- **Email/export notifications** — a simple hook to notify staff when a new export is ready, without them needing to check the app
- **Multi-user support** — right now this is a single-user local app; if it ever moves to a shared server, it would need authentication and per-user audit logs
- **Scheduled runs** — automatically re-run the pipeline on a cron schedule when new files are dropped into a watched folder
- **Test coverage** — the validation logic has been manually tested but deserves a proper pytest suite, especially around the date parsing and duplicate detection edge cases

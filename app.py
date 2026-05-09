import os
import json
import uuid

from flask import Flask, render_template, request, redirect, url_for, flash, session

from database.models import init_db, get_connection
from ingestion.intake import parse_file
from ingestion.validator import validate

app = Flask(__name__)
app.config["SECRET_KEY"] = "netter-pipeline-local"

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _allowed(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Home — run history
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    conn = get_connection()
    runs = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY run_at DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return render_template("index.html", runs=runs)


# ---------------------------------------------------------------------------
# Upload — GET shows form, POST processes file
# ---------------------------------------------------------------------------
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("upload.html")

    # ------------------------------------------------------------------
    # 1. Basic form validation
    # ------------------------------------------------------------------
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "error")
        return render_template("upload.html")

    if not _allowed(file.filename):
        flash("Unsupported file type. Please upload .xlsx, .xls, or .csv.", "error")
        return render_template("upload.html")

    program_name = request.form.get("program", "").strip()
    school       = request.form.get("school", "").strip()
    category     = request.form.get("category", "").strip()
    date_range   = request.form.get("date_range", "").strip()

    if not program_name or not school or not category:
        flash("Program, school, and category are required.", "error")
        return render_template("upload.html")

    # ------------------------------------------------------------------
    # 2. Save file temporarily
    # ------------------------------------------------------------------
    ext       = os.path.splitext(file.filename)[1].lower()
    tmp_name  = f"{uuid.uuid4().hex}{ext}"
    tmp_path  = os.path.join(UPLOAD_FOLDER, tmp_name)
    file.save(tmp_path)

    # ------------------------------------------------------------------
    # 3. Parse
    # ------------------------------------------------------------------
    parse_result = parse_file(tmp_path)
    if not parse_result.ok:
        os.remove(tmp_path)
        return render_template(
            "upload.html",
            parse_errors=parse_result.errors,
            form=request.form,
        )

    # ------------------------------------------------------------------
    # 4. Validate
    # ------------------------------------------------------------------
    val_result = validate(parse_result.df)

    # ------------------------------------------------------------------
    # 5. Persist to DB regardless of validation outcome
    #    (so we can show a history of attempted uploads)
    # ------------------------------------------------------------------
    conn = get_connection()
    with conn:
        # Upsert program
        existing = conn.execute(
            "SELECT id FROM programs WHERE name = ? AND school = ?",
            (program_name, school),
        ).fetchone()

        if existing:
            program_id = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO programs (name, school, category) VALUES (?, ?, ?)",
                (program_name, school, category),
            )
            program_id = cur.lastrowid

        # Record the upload
        cur = conn.execute(
            """INSERT INTO uploads (program_id, filename, date_range, total_rows, status)
               VALUES (?, ?, ?, ?, ?)""",
            (
                program_id,
                file.filename,
                date_range,
                val_result.stats.get("total_rows", 0),
                "valid" if val_result.valid else "invalid",
            ),
        )
        upload_id = cur.lastrowid

        # Store raw rows (only when parse succeeded)
        if val_result.valid and val_result.df is not None:
            rows = val_result.df.fillna("").to_dict(orient="records")
            for row in rows:
                # Convert dates to ISO strings for JSON storage
                if hasattr(row.get("date"), "isoformat"):
                    row["date"] = row["date"].isoformat()
                conn.execute(
                    "INSERT INTO attendance_raw (program_id, upload_id, raw_data) VALUES (?, ?, ?)",
                    (program_id, upload_id, json.dumps(row)),
                )

    conn.close()
    os.remove(tmp_path)

    # ------------------------------------------------------------------
    # 6. Redirect or show errors
    # ------------------------------------------------------------------
    if val_result.valid:
        session["upload_id"]   = upload_id
        session["program_id"]  = program_id
        session["program_name"] = program_name
        flash(
            f"File validated successfully — {val_result.stats['total_rows']} records ready for review.",
            "success",
        )
        return redirect(url_for("review"))

    return render_template(
        "upload.html",
        val_result=val_result,
        form=request.form,
    )


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------
@app.route("/review")
def review():
    upload_id  = session.get("upload_id")
    program_id = session.get("program_id")

    if not upload_id:
        flash("No upload in progress. Please upload a file first.", "warning")
        return redirect(url_for("upload"))

    conn = get_connection()
    rows = conn.execute(
        "SELECT raw_data FROM attendance_raw WHERE upload_id = ? ORDER BY id",
        (upload_id,),
    ).fetchall()
    conn.close()

    records = [json.loads(r["raw_data"]) for r in rows]
    total   = len(records)
    matched = sum(1 for r in records if r.get("matched"))

    return render_template(
        "review.html",
        records=records,
        total=total,
        matched=matched,
        flagged=0,
        program_name=session.get("program_name", ""),
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)

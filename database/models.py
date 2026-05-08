import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "db.sqlite")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS programs (
                id       INTEGER PRIMARY KEY,
                name     TEXT NOT NULL,
                school   TEXT,
                category TEXT
            );

            CREATE TABLE IF NOT EXISTS attendance_raw (
                id          INTEGER PRIMARY KEY,
                program_id  INTEGER REFERENCES programs(id),
                upload_id   INTEGER,
                raw_data    JSON,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attendance_clean (
                id                 INTEGER PRIMARY KEY,
                program_id         INTEGER REFERENCES programs(id),
                student_id         TEXT,
                date               DATE,
                present            BOOLEAN,
                citispan_compliant BOOLEAN,
                matched            BOOLEAN,
                run_id             INTEGER REFERENCES pipeline_runs(id)
            );

            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id                INTEGER PRIMARY KEY,
                run_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                files_ingested    INTEGER,
                records_processed INTEGER,
                records_flagged   INTEGER,
                export_path       TEXT
            );
        """)
    conn.close()

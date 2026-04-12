"""
Database configuration and session management for SPAM application.
"""
import os
import sqlite3
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database URL - using SQLite for local storage
# Database file will be created in the same directory as this script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_FILE = os.path.join(BASE_DIR, "spam.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# Create SQLAlchemy engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False  # Set to True for SQL query logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()


def migrate_db():
    """Add any missing columns to existing tables so the app works with old DBs."""
    if not os.path.exists(DATABASE_FILE):
        return
    conn = sqlite3.connect(DATABASE_FILE)
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(measurements)").fetchall()}
        migrations = [
            ("transmitted_power", "REAL"),
            ("reflected_power",   "REAL"),
            ("transmitted_phase",  "REAL"),
            ("reflected_phase",    "REAL"),
            ("s_matrix_json",      "TEXT"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE measurements ADD COLUMN {col_name} {col_type}")
        # Ensure calibration_sweeps table exists (created by ORM on fresh DBs;
        # this handles the case where the DB was created before this model was added).
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "calibration_sweeps" not in tables:
            conn.execute("""
                CREATE TABLE calibration_sweeps (
                    id INTEGER PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    sweep_type TEXT NOT NULL,
                    angles_json TEXT,
                    voltages_json TEXT,
                    geometry_json TEXT,
                    f0_ghz REAL
                )
            """)
        conn.commit()
    finally:
        conn.close()


migrate_db()

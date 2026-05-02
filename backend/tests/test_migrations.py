import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_alembic_upgrade_head_creates_institutional_tables(tmp_path):
    db_path = tmp_path / "migration.db"
    backend_dir = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        "JWT_SECRET_KEY": "ci-test-secret-32-bytes-long-enough",
    }

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "select name from sqlite_master where type='table'"
            ).fetchall()
        }
    assert {"event_reviews", "admin_job_runs", "disclosure_evidence", "alembic_version"} <= tables

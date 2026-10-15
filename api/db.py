import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "game.db"


def get_connection() -> sqlite3.Connection:
    """Atver spēles SQLite datubāzi un nodrošina vajadzīgās tabulas."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            name TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            token TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player TEXT NOT NULL,
            score INTEGER NOT NULL CHECK(score >= 1),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(player) REFERENCES players(name)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            player TEXT PRIMARY KEY,
            max_unlocked_map INTEGER NOT NULL DEFAULT 1,
            skill_points INTEGER NOT NULL DEFAULT 2,
            skills_json TEXT NOT NULL DEFAULT '{}',
            infinite_unlocked INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(player) REFERENCES players(name)
        )
        """
    )
    return conn

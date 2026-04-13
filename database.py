import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "tracker.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        );

        -- Stores password reset tokens
        -- token: random 32-char string sent to user's email
        -- expires_at: token becomes invalid after this datetime
        -- used: once redeemed, marked 1 so it can never be reused
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token      TEXT    NOT NULL UNIQUE,
            expires_at TEXT    NOT NULL,
            used       INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL,
            type        TEXT    NOT NULL CHECK(type IN ('habit','task')),
            completed   INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id   INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
            log_date  TEXT    NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            UNIQUE(item_id, log_date)
        );

        CREATE TABLE IF NOT EXISTS daily_points (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            log_date      TEXT    NOT NULL,
            habit_points  INTEGER NOT NULL DEFAULT 0,
            task_points   INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, log_date)
        );
    """)
    db.commit()
    db.close()

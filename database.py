"""
database.py — Database backend for AI Startup Agent.

Tries Neon (PostgreSQL) first. If the connection fails (e.g. firewall
blocking port 5432), falls back to a local SQLite database so the app
keeps working offline.

Requires DATABASE_URL in .env for Neon:
    DATABASE_URL=postgresql://user:password@ep-xxx.neon.tech/neondb?sslmode=require
"""

import os
import sqlite3
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
_USE_SQLITE = False  # Set to True at runtime if Neon is unreachable
_SQLITE_PATH = os.path.join(os.path.dirname(__file__), "startup_ideas.db")


def _get_conn():
    """Return a database connection — Neon (PostgreSQL) or local SQLite fallback."""
    global _USE_SQLITE

    if _USE_SQLITE:
        return sqlite3.connect(_SQLITE_PATH)

    if not DATABASE_URL:
        _USE_SQLITE = True
        print("[database] No DATABASE_URL set. Using local SQLite.")
        return sqlite3.connect(_SQLITE_PATH)

    try:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, connect_timeout=5)
    except Exception as e:
        print(f"[database] Neon connection failed: {e}. Falling back to SQLite.")
        _USE_SQLITE = True
        return sqlite3.connect(_SQLITE_PATH)


def _placeholder():
    """Return the correct placeholder for the active backend."""
    return "?" if _USE_SQLITE else "%s"


# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────

def init_db():
    """
    Create tables if they don't exist.
    Works with both PostgreSQL (Neon) and SQLite.
    """
    conn = _get_conn()
    cur = conn.cursor()

    if _USE_SQLITE:
        # SQLite schema
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ideas (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp        TEXT NOT NULL DEFAULT (datetime('now')),
                topic            TEXT NOT NULL,
                sector           TEXT,
                team_size        TEXT,
                budget           TEXT,
                pain_point       TEXT,
                idea_name        TEXT NOT NULL,
                idea_description TEXT NOT NULL,
                analysis         TEXT,
                verdict          TEXT,
                score            REAL,
                explanation      TEXT,
                bull_summary     TEXT,
                bear_summary     TEXT,
                embedding        BLOB
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pain_points (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
                topic       TEXT NOT NULL,
                pain_point  TEXT NOT NULL,
                embedding   BLOB
            )
        """)
    else:
        # PostgreSQL schema
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ideas (
                id               SERIAL PRIMARY KEY,
                timestamp        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                topic            TEXT NOT NULL,
                sector           TEXT,
                team_size        TEXT,
                budget           TEXT,
                pain_point       TEXT,
                idea_name        TEXT NOT NULL,
                idea_description TEXT NOT NULL,
                analysis         TEXT,
                verdict          TEXT,
                score            REAL,
                explanation      TEXT,
                bull_summary     TEXT,
                bear_summary     TEXT,
                embedding        BYTEA
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pain_points (
                id          SERIAL PRIMARY KEY,
                timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                topic       TEXT NOT NULL,
                pain_point  TEXT NOT NULL,
                embedding   BYTEA
            )
        """)

    conn.commit()
    cur.close()
    conn.close()


# ─────────────────────────────────────────────
# IDEAS
# ─────────────────────────────────────────────

def save_idea(
    topic: str,
    idea_name: str,
    idea_description: str,
    analysis: str = "",
    verdict: str = "",
    score: float = None,
    explanation: str = "",
    bull_summary: str = "",
    bear_summary: str = "",
    pain_point: str = "",
    sector: str = "",
    team_size: str = "",
    budget: str = "",
    embedding: bytes = None,
):
    """Save a judge-approved startup idea with all fields stored in separate columns."""
    # Generate embedding from idea name + description if not provided
    if embedding is None:
        try:
            from embeddings import embed_text
            emb_arr = embed_text(f"{idea_name}\n\n{idea_description}")
            embedding = emb_arr.tobytes()
        except Exception:
            embedding = None

    conn = _get_conn()
    ph = _placeholder()  # Must be called AFTER _get_conn() sets _USE_SQLITE correctly
    cur = conn.cursor()
    cur.execute(f"""
        INSERT INTO ideas (
            topic, sector, team_size, budget, pain_point,
            idea_name, idea_description, analysis,
            verdict, score, explanation, bull_summary, bear_summary,
            embedding
        ) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
    """, (
        topic, sector, team_size, budget, pain_point,
        idea_name, idea_description, analysis,
        verdict, score, explanation, bull_summary, bear_summary,
        embedding,
    ))
    conn.commit()
    cur.close()
    conn.close()


def get_all_ideas():
    """Retrieve all saved startup ideas, latest first."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, timestamp, topic, sector, team_size, budget, pain_point,
               idea_name, idea_description, analysis,
               verdict, score, explanation, bull_summary, bear_summary, embedding
        FROM ideas
        ORDER BY id DESC
    """)
    records = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id":               r[0],
            "timestamp":        str(r[1]),
            "topic":            r[2],
            "sector":           r[3],
            "team_size":        r[4],
            "budget":           r[5],
            "pain_point":       r[6],
            "idea_name":        r[7],
            # "idea_content" kept as alias so sidebar UI code doesn't break
            "idea_content":     r[8],
            "idea_description": r[8],
            "analysis":         r[9],
            "verdict":          r[10],
            "score":            r[11],
            "explanation":      r[12],
            "bull_summary":     r[13],
            "bear_summary":     r[14],
            "embedding":        r[15],
        }
        for r in records
    ]


def delete_idea(idea_id: int):
    """Delete a specific startup idea by ID."""
    conn = _get_conn()
    ph = _placeholder()  # Must be called AFTER _get_conn() sets _USE_SQLITE correctly
    cur = conn.cursor()
    cur.execute(f"DELETE FROM ideas WHERE id = {ph}", (idea_id,))
    conn.commit()
    cur.close()
    conn.close()


# ─────────────────────────────────────────────
# PAIN POINTS MEMORY
# ─────────────────────────────────────────────

def save_generated_pain_point(topic: str, pain_point: str, embedding: bytes = None):
    """Save a generated pain point to the memory table."""
    if embedding is None:
        try:
            from embeddings import embed_text
            embedding = embed_text(pain_point).tobytes()
        except Exception:
            embedding = None

    conn = _get_conn()
    ph = _placeholder()  # Must be called AFTER _get_conn() sets _USE_SQLITE correctly
    cur = conn.cursor()
    cur.execute(f"""
        INSERT INTO pain_points (topic, pain_point, embedding)
        VALUES ({ph}, {ph}, {ph})
    """, (topic, pain_point, embedding))
    conn.commit()
    cur.close()
    conn.close()


def get_all_generated_pain_points():
    """Retrieve all stored pain points from memory."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, timestamp, topic, pain_point, embedding
        FROM pain_points
        ORDER BY id DESC
    """)
    records = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id":         r[0],
            "timestamp":  str(r[1]),
            "topic":      r[2],
            "pain_point": r[3],
            "embedding":  r[4],
        }
        for r in records
    ]

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
import datetime
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
                vc_report        TEXT,
                embedding        BLOB
            )
        """)
        # Schema migration: Check if vc_report column exists in sqlite
        try:
            cur.execute("ALTER TABLE ideas ADD COLUMN vc_report TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Column already exists
            pass

        cur.execute("""
            CREATE TABLE IF NOT EXISTS pain_points (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
                topic       TEXT NOT NULL,
                pain_point  TEXT NOT NULL,
                embedding   BLOB
            )
        """)

        # User-submitted startup evaluations
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_ideas (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp         TEXT NOT NULL DEFAULT (datetime('now')),
                startup_name      TEXT NOT NULL,
                domain            TEXT,
                sector            TEXT,
                stage             TEXT,
                monthly_revenue   TEXT,
                annual_turnover   TEXT,
                team_size         TEXT,
                description       TEXT,
                problem_solved    TEXT,
                target_customer   TEXT,
                competitors       TEXT,
                funding_sought    TEXT,
                readiness_score   REAL,
                dimension_scores  TEXT,
                feedback          TEXT,
                suggestions       TEXT,
                vc_report         TEXT
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
                vc_report        TEXT,
                embedding        BYTEA
            )
        """)
        # Schema migration: Check if vc_report column exists in pg
        try:
            cur.execute("ALTER TABLE ideas ADD COLUMN IF NOT EXISTS vc_report TEXT")
            conn.commit()
        except Exception:
            pass

        cur.execute("""
            CREATE TABLE IF NOT EXISTS pain_points (
                id          SERIAL PRIMARY KEY,
                timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                topic       TEXT NOT NULL,
                pain_point  TEXT NOT NULL,
                embedding   BYTEA
            )
        """)

        # User-submitted startup evaluations
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_ideas (
                id                SERIAL PRIMARY KEY,
                timestamp         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                startup_name      TEXT NOT NULL,
                domain            TEXT,
                sector            TEXT,
                stage             TEXT,
                monthly_revenue   TEXT,
                annual_turnover   TEXT,
                team_size         TEXT,
                description       TEXT,
                problem_solved    TEXT,
                target_customer   TEXT,
                competitors       TEXT,
                funding_sought    TEXT,
                readiness_score   REAL,
                dimension_scores  TEXT,
                feedback          TEXT,
                suggestions       TEXT,
                vc_report         TEXT
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
    vc_report: str = "",
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
    
    # Generate timestamp manually to support pre-existing SQLite database schema
    now_str = datetime.datetime.utcnow().isoformat()
    
    cur.execute(f"""
        INSERT INTO ideas (
            timestamp, topic, sector, team_size, budget, pain_point,
            idea_name, idea_description, analysis,
            verdict, score, explanation, bull_summary, bear_summary,
            vc_report, embedding
        ) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
    """, (
        now_str, topic, sector, team_size, budget, pain_point,
        idea_name, idea_description, analysis,
        verdict, score, explanation, bull_summary, bear_summary,
        vc_report, embedding,
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
               verdict, score, explanation, bull_summary, bear_summary, vc_report, embedding
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
            "vc_report":        r[15],
            "embedding":        r[16],
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
    
    # Generate timestamp manually to support pre-existing SQLite database schema
    now_str = datetime.datetime.utcnow().isoformat()
    
    cur.execute(f"""
        INSERT INTO pain_points (timestamp, topic, pain_point, embedding)
        VALUES ({ph}, {ph}, {ph}, {ph})
    """, (now_str, topic, pain_point, embedding))
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


# ─────────────────────────────────────────────
# USER-SUBMITTED IDEAS (Pitch My Idea)
# ─────────────────────────────────────────────

def save_user_idea(
    startup_name: str,
    domain: str = "",
    sector: str = "",
    stage: str = "",
    monthly_revenue: str = "",
    annual_turnover: str = "",
    team_size: str = "",
    description: str = "",
    problem_solved: str = "",
    target_customer: str = "",
    competitors: str = "",
    funding_sought: str = "",
    readiness_score: float = None,
    dimension_scores: str = "",
    feedback: str = "",
    suggestions: str = "",
    vc_report: str = "",
):
    """Save a user-submitted startup evaluation."""
    conn = _get_conn()
    ph = _placeholder()
    cur = conn.cursor()
    now_str = datetime.datetime.utcnow().isoformat()

    cur.execute(f"""
        INSERT INTO user_ideas (
            timestamp, startup_name, domain, sector, stage,
            monthly_revenue, annual_turnover, team_size,
            description, problem_solved, target_customer, competitors,
            funding_sought, readiness_score, dimension_scores,
            feedback, suggestions, vc_report
        ) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
    """, (
        now_str, startup_name, domain, sector, stage,
        monthly_revenue, annual_turnover, team_size,
        description, problem_solved, target_customer, competitors,
        funding_sought, readiness_score, dimension_scores,
        feedback, suggestions, vc_report,
    ))
    conn.commit()
    cur.close()
    conn.close()


def get_all_user_ideas():
    """Retrieve all user-submitted startup evaluations, latest first."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, timestamp, startup_name, domain, sector, stage,
               monthly_revenue, annual_turnover, team_size,
               description, problem_solved, target_customer, competitors,
               funding_sought, readiness_score, dimension_scores,
               feedback, suggestions, vc_report
        FROM user_ideas
        ORDER BY id DESC
    """)
    records = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id":               r[0],
            "timestamp":        str(r[1]),
            "startup_name":     r[2],
            "domain":           r[3],
            "sector":           r[4],
            "stage":            r[5],
            "monthly_revenue":  r[6],
            "annual_turnover":  r[7],
            "team_size":        r[8],
            "description":      r[9],
            "problem_solved":   r[10],
            "target_customer":  r[11],
            "competitors":      r[12],
            "funding_sought":   r[13],
            "readiness_score":  r[14],
            "dimension_scores": r[15],
            "feedback":         r[16],
            "suggestions":      r[17],
            "vc_report":        r[18],
        }
        for r in records
    ]


def delete_user_idea(idea_id: int):
    """Delete a user-submitted idea by ID."""
    conn = _get_conn()
    ph = _placeholder()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM user_ideas WHERE id = {ph}", (idea_id,))
    conn.commit()
    cur.close()
    conn.close()

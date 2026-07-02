import sqlite3
from datetime import datetime

DB_NAME = "startup_ideas.db"


def init_db():
    """Create the startup ideas table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            topic TEXT NOT NULL,
            idea_name TEXT NOT NULL,
            idea_content TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_idea(topic: str, idea_name: str, idea_content: str):
    """Save a judge-approved startup idea to the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO ideas (timestamp, topic, idea_name, idea_content)
        VALUES (?, ?, ?, ?)
    """, (timestamp, topic, idea_name, idea_content))
    conn.commit()
    conn.close()


def get_all_ideas():
    """Retrieve all saved startup ideas, latest first."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, topic, idea_name, idea_content 
        FROM ideas 
        ORDER BY id DESC
    """)
    records = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "topic": r[2],
            "idea_name": r[3],
            "idea_content": r[4],
        }
        for r in records
    ]


def delete_idea(idea_id: int):
    """Delete a specific startup idea by ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
    conn.commit()
    conn.close()

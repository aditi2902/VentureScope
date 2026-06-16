import sqlite3
from datetime import datetime

DB_NAME = "startup_ideas.db"


def init_db():
    """Create the startup ideas and pain points tables if they don't exist, and migrate if needed."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Existing ideas table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            topic TEXT NOT NULL,
            idea_name TEXT NOT NULL,
            idea_content TEXT NOT NULL
        )
    """)
    
    # Check if 'embedding' column exists in ideas
    cursor.execute("PRAGMA table_info(ideas)")
    columns = [col[1] for col in cursor.fetchall()]
    if "embedding" not in columns:
        cursor.execute("ALTER TABLE ideas ADD COLUMN embedding BLOB")
        conn.commit()
        
    # Backfill missing embeddings for ideas
    cursor.execute("SELECT id, idea_name, idea_content FROM ideas WHERE embedding IS NULL")
    missing = cursor.fetchall()
    if missing:
        try:
            from embeddings import embed_text
            for row_id, name, content in missing:
                text_to_embed = f"{name}\n\n{content}"
                emb_arr = embed_text(text_to_embed)
                cursor.execute(
                    "UPDATE ideas SET embedding = ? WHERE id = ?",
                    (emb_arr.tobytes(), row_id)
                )
            conn.commit()
        except Exception as e:
            pass

    # NEW: pain_points memory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pain_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            topic TEXT NOT NULL,
            pain_point TEXT NOT NULL,
            embedding BLOB
        )
    """)
    conn.commit()
    conn.close()


def save_idea(topic: str, idea_name: str, idea_content: str, embedding: bytes = None):
    """Save a judge-approved startup idea to the database, along with its embedding."""
    if embedding is None:
        try:
            from embeddings import embed_text
            text_to_embed = f"{idea_name}\n\n{idea_content}"
            emb_arr = embed_text(text_to_embed)
            embedding = emb_arr.tobytes()
        except Exception as e:
            embedding = None

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO ideas (timestamp, topic, idea_name, idea_content, embedding)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, topic, idea_name, idea_content, embedding))
    conn.commit()
    conn.close()


def get_all_ideas():
    """Retrieve all saved startup ideas, latest first."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, topic, idea_name, idea_content, embedding 
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
            "embedding": r[5],
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


def save_generated_pain_point(topic: str, pain_point: str, embedding: bytes = None):
    """Save a generated pain point to the memory table with its embedding."""
    if embedding is None:
        try:
            from embeddings import embed_text
            emb_arr = embed_text(pain_point)
            embedding = emb_arr.tobytes()
        except Exception as e:
            embedding = None

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO pain_points (timestamp, topic, pain_point, embedding)
        VALUES (?, ?, ?, ?)
    """, (timestamp, topic, pain_point, embedding))
    conn.commit()
    conn.close()


def get_all_generated_pain_points():
    """Retrieve all stored pain points from memory."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, topic, pain_point, embedding 
        FROM pain_points 
        ORDER BY id DESC
    """)
    records = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "topic": r[2],
            "pain_point": r[3],
            "embedding": r[4],
        }
        for r in records
    ]



import sqlite3

DB_PATH = "data/filmes.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def inicializar_banco():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filmes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id INTEGER NOT NULL UNIQUE
        )
    """)

    conn.commit()
    conn.close()

def adicionar_filme(tmdb_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO filmes (tmdb_id) VALUES (?)",
            (tmdb_id,)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_filme_aleatorio():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT tmdb_id FROM filmes ORDER BY RANDOM() LIMIT 1")
    resultado = cursor.fetchone()

    conn.close()

    if resultado:
        return resultado[0]
    return None
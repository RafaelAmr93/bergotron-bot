import sqlite3

DB_PATH = "filmes.db"

def conectar():
    return sqlite3.connect(DB_PATH)

def inicializar_banco():
    with conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS filmes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tmdb_id INTEGER NOT NULL UNIQUE
            )
        """)
        conn.commit()

def adicionar_filme(tmdb_id: int) -> bool:
    if not isinstance(tmdb_id, int):
        raise ValueError("tmdb_id invalido")

    with conectar() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM filmes WHERE tmdb_id = ?",
            (tmdb_id,)
        )
        if cursor.fetchone():
            return False

        cursor.execute(
            "INSERT INTO filmes (tmdb_id) VALUES (?)",
            (tmdb_id,)
        )
        conn.commit()
        return True

def get_filme_aleatorio():
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tmdb_id FROM filmes ORDER BY RANDOM() LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None
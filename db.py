import sqlite3
import random
import os

DB_PATH = "data/filmes.db"

def init_db():
    # Garante que a pasta data exista localmente ou no contêiner
    os.makedirs("data", exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Cria a tabela armazenando apenas o ID do filme na API do TMDB
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS filmes (
            id INTEGER PRIMARY KEY
        )
    ''')
    
    # Verifica se o banco está vazio. Se estiver, insere a lista de IDs de teste.
    cursor.execute("SELECT COUNT(*) FROM filmes")
    if cursor.fetchone()[0] == 0:
        # Lista expandida com filmes populares do TMDB 
        # Mistura de blockbusters, clássicos, sci-fi e dramas
        filmes_iniciais = [
            (475557,),  # Dark Waters
            (2259,),    # Crash (2004)
            (603,),     # The Matrix
            (157336,),  # Interstellar
            (155,),     # The Dark Knight
            (27205,),   # Inception
            (19995,),   # Avatar
            (680,),     # Pulp Fiction
            (550,),     # Fight Club
            (13,),      # Forrest Gump
            (120,),     # The Lord of the Rings: The Fellowship of the Ring
            (129,),     # Spirited Away (A Viagem de Chihiro)
            (496243,),  # Parasite
            (533535,),  # Deadpool & Wolverine
            (1022789,), # Inside Out 2 (Divertida Mente 2)
            (872585,),  # Oppenheimer
            (346698,),  # Barbie
            (118340,),  # Guardians of the Galaxy
            (76341,),   # Mad Max: Fury Road
            (2898,),    # As Good as It Gets
            (420830,)   # Blame! (Filme)
        ]
        
        cursor.executemany("INSERT INTO filmes (id) VALUES (?)", filmes_iniciais)
        conn.commit()
        print(f"Banco inicializado com {len(filmes_iniciais)} filmes populares!")
        
    conn.close()

def get_filme_aleatorio():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # O SQLite tem uma função nativa muito rápida para sortear
    cursor.execute("SELECT id FROM filmes ORDER BY RANDOM() LIMIT 1")
    resultado = cursor.fetchone()
    
    conn.close()
    
    if resultado:
        return resultado[0]
    return None

# Executa a inicialização quando o arquivo for importado
init_db()
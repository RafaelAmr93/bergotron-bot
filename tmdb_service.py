import aiohttp
import os

async def buscar_filme(filme_id):
    api_key = os.getenv('TMDB_API_KEY')
    
    if not api_key:
        print("Erro: TMDB_API_KEY nao encontrada.")
        return None

    url = f"https://api.themoviedb.org/3/movie/{filme_id}"
    params = {
        "api_key": api_key,
        "language": "pt-BR"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    dados = await response.json()
                    return {
                        "titulo": dados.get("title"),
                        "sinopse": dados.get("overview")
                    }
                else:
                    print(f"Erro na API do TMDB: Status {response.status}")
                    return None
        except Exception as e:
            print(f"Erro ao conectar com TMDB: {e}")
            return None
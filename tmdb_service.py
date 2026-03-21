import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")

async def buscar_filme(filme_id: int):
    url = f"https://api.themoviedb.org/3/movie/{filme_id}"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "pt-BR",
        "append_to_response": "credits,keywords,release_dates,videos"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                print(f"Erro TMDB: status {resp.status}")
                return None

            data = await resp.json()

    crew = data.get("credits", {}).get("crew", [])
    cast = data.get("credits", {}).get("cast", [])
    keywords_block = data.get("keywords", {}).get("keywords", [])

    diretores = [p["name"] for p in crew if p.get("job") == "Director"][:2]
    roteiristas = [
        p["name"] for p in crew
        if p.get("job") in ("Writer", "Screenplay")
    ][:3]
    elenco = [p["name"] for p in cast[:5]]
    keywords = [k["name"] for k in keywords_block[:8]]
    generos = [g["name"] for g in data.get("genres", [])[:4]]

    return {
        "id": data.get("id"),
        "titulo": data.get("title"),
        "titulo_original": data.get("original_title"),
        "sinopse": data.get("overview"),
        "tagline": data.get("tagline"),
        "ano": (data.get("release_date") or "")[:4],
        "duracao": data.get("runtime"),
        "generos": generos,
        "diretores": diretores,
        "roteiristas": roteiristas,
        "elenco": elenco,
        "keywords": keywords,
        "nota": data.get("vote_average"),
        "votos": data.get("vote_count"),
        "idioma_original": data.get("original_language"),
        "popularidade": data.get("popularity"),
    }
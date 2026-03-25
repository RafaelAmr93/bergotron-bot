import os
import re
import unicodedata
import aiohttp
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")


def _normalizar_titulo(texto: str) -> str:
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _extrair_titulo_e_ano(texto: str):
    texto = texto.strip()

    # Aceita:
    # "Brokeback Mountain (2005)"
    # "Brokeback Mountain 2005"
    # "Brokeback Mountain"
    match = re.match(r"^(.*?)(?:\s*\((\d{4})\)|\s+(\d{4}))?$", texto)
    if not match:
        return texto, None

    titulo = (match.group(1) or "").strip()
    ano = match.group(2) or match.group(3)

    return titulo, str(ano) if ano else None


def _simplificar_resultado(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "titulo": item.get("title"),
        "titulo_original": item.get("original_title"),
        "ano": (item.get("release_date") or "")[:4],
        "popularidade": item.get("popularity", 0),
    }


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


async def buscar_filme_por_nome(nome: str):
    titulo_busca, ano_busca = _extrair_titulo_e_ano(nome)

    if not titulo_busca:
        return {"status": "nenhum", "resultados": []}

    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "language": "pt-BR",
        "query": titulo_busca,
        "include_adult": "false"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                print(f"Erro TMDB busca por nome: status {resp.status}")
                return {"status": "erro"}

            data = await resp.json()

    resultados_brutos = data.get("results", [])
    if not resultados_brutos:
        return {"status": "nenhum", "resultados": []}

    resultados = [_simplificar_resultado(item) for item in resultados_brutos]

    titulo_normalizado = _normalizar_titulo(titulo_busca)

    # 1) Se o usuário passou ano, tenta reduzir por ano
    if ano_busca:
        por_ano = [r for r in resultados if r.get("ano") == ano_busca]
        if len(por_ano) == 1:
            filme = await buscar_filme(int(por_ano[0]["id"]))
            return {"status": "ok", "filme": filme}

        if len(por_ano) > 1:
            resultados = por_ano

    # 2) Tenta casar por título exato normalizado
    exatos = [
        r for r in resultados
        if _normalizar_titulo(r.get("titulo") or "") == titulo_normalizado
        or _normalizar_titulo(r.get("titulo_original") or "") == titulo_normalizado
    ]

    if len(exatos) == 1:
        filme = await buscar_filme(int(exatos[0]["id"]))
        return {"status": "ok", "filme": filme}

    if len(resultados) == 1:
        filme = await buscar_filme(int(resultados[0]["id"]))
        return {"status": "ok", "filme": filme}

    # Ordena por popularidade para mostrar opções mais úteis
    resultados = sorted(
        resultados,
        key=lambda r: r.get("popularidade", 0),
        reverse=True
    )

    return {
        "status": "multiplo",
        "resultados": resultados[:5]
    }
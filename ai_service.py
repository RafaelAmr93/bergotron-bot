import aiohttp
import re
import asyncio

PROMPT_BASE = """
Voce e o Bergotron, um recomendador de filmes elegante, persuasivo e natural.
Seu objetivo nao e resumir o filme: e convencer alguem a dar play.

Regras:
- fale como quem realmente conhece o filme;
- use elementos concretos da sinopse, direcao, elenco, generos e reputacao;
- nao use spoiler;
- nao seja generico;
- nao liste fatos de forma seca;
- transforme os dados em argumento;
- escreva em tom falado, para leitura em voz alta;
- escreva entre 60 e 100 palavras;
- escreva entre 4 e 6 frases;
- nao repita ideias;
- nao reescreva a mesma frase com outras palavras;
- nao use metacomentarios como "primeiro", "depois", "vamos la", "olha so", "em resumo";
- termine exatamente uma unica vez com: Pode colocar sem medo.
"""

def montar_contexto_filme(filme):
    return (
        f"Titulo: {filme.get('titulo')} ({filme.get('ano')})\n"
        f"Direcao: {', '.join(filme.get('diretores', []))}\n"
        f"Generos: {', '.join(filme.get('generos', []))}\n"
        f"Elenco: {', '.join(filme.get('elenco', [])[:3])}\n"
        f"Sinopse: {filme.get('sinopse')}\n"
        f"Keywords: {', '.join(filme.get('keywords', [])[:5])}\n"
        f"Nota TMDB: {filme.get('nota')}/10"
    )

def limpar_texto_tts(texto: str) -> str:
    texto = (texto or "").strip()
    texto = re.sub(r"\s+", " ", texto).strip()

    frases = re.split(r"(?<=[.!?])\s+", texto)

    frases_limpas = []
    chaves_vistas = set()
    inicios_vistos = set()

    for frase in frases:
        frase = frase.strip()
        if not frase:
            continue

        chave = frase.lower()
        inicio = " ".join(chave.split()[:8])

        if chave in chaves_vistas or inicio in inicios_vistos:
            continue

        chaves_vistas.add(chave)
        inicios_vistos.add(inicio)
        frases_limpas.append(frase)

    texto = " ".join(frases_limpas)

    texto = re.sub(
        r"(Pode colocar sem medo\.?\s*)+",
        "Pode colocar sem medo.",
        texto,
        flags=re.IGNORECASE
    )

    return texto.strip()

async def gerar_recomendacao(filme):
    contexto_filme = montar_contexto_filme(filme)
    
    prompt = f"""
    {PROMPT_BASE}
    
    DADOS DO FILME:
    {contexto_filme}
    """

    # URL padrão da API local do Ollama
    url = "http://host.docker.internal:11434/api/generate"
    
    payload = {
        "model": "gemma2",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.75,
            "num_predict": 250 # Controla o tamanho da saída
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Aumentei o timeout porque rodar localmente na primeira vez pode demorar
            print("Enviando prompt para o Ollama local...")
            async with session.post(url, json=payload, timeout=60) as response:
                if response.status == 200:
                    dados = await response.json()
                    texto_bruto = dados.get("response", "").strip()
                    texto_limpo = limpar_texto_tts(texto_bruto)
                    return texto_limpo
                else:
                    print(f"Erro no Ollama. Status: {response.status}")
                    
    except asyncio.TimeoutError:
         print("O modelo demorou muito para responder (Timeout).")
    except Exception as e:
        print(f"Erro de conexão com o Ollama: {e}")

    # Fallback caso tudo falhe ou o Ollama esteja desligado
    return (
        f"{filme.get('titulo')} parece daqueles filmes que ja se vendem pela proposta. "
        f"A combinacao de {', '.join(filme.get('generos', [])[:2]) or 'uma boa premissa'} "
        f"com a atmosfera sugerida pela sinopse indica uma experiencia que tem identidade. "
        f"Pode colocar sem medo."
    )
import os
import re
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

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
- escreva entre 90 e 140 palavras;
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
    if not api_key:
        return "Erro: GEMINI_API_KEY nao encontrada."

    contexto_filme = montar_contexto_filme(filme)

    prompt = f"""
{PROMPT_BASE}

Use os dados do TMDB abaixo como base principal.
Se for util, faca busca na web para complementar com no maximo 2 pontos:
- recepcao critica
- relevancia cultural
- destaque da direcao ou do elenco

DADOS DO FILME:
{contexto_filme}
"""

    try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    system_instruction=(
                        "Escreva como um recomendador de filmes que sabe vender a experiencia do filme. "
                        "Seja especifico, elegante, persuasivo e sem repeticao."
                    ),
                    temperature=0.75,
                    max_output_tokens=260,
                ),
            ),
            timeout=20,
        )

        texto = limpar_texto_tts((response.text or "").strip())
        if texto:
            return texto

    except Exception as e:
        print(f"Erro na geracao com busca: {e}")

    try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=(
                    f"{PROMPT_BASE}\n\n"
                    f"DADOS DO FILME:\n{contexto_filme}"
                ),
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "Escreva uma recomendacao oral de filme com personalidade, "
                        "mais sofisticada e convincente, sem repeticao."
                    ),
                    temperature=0.75,
                    max_output_tokens=220,
                ),
            ),
            timeout=12,
        )

        texto = limpar_texto_tts((response.text or "").strip())
        if texto:
            return texto

    except Exception as e:
        print(f"Erro na geracao fallback: {e}")

    return (
        f"{filme.get('titulo')} parece daqueles filmes que ja se vendem pela proposta. "
        f"A combinacao de {', '.join(filme.get('generos', [])[:2]) or 'uma boa premissa'} "
        f"com a atmosfera sugerida pela sinopse indica uma experiencia que tem identidade, peso e personalidade. "
        f"Nao e so mais uma opcao aleatoria para preencher tempo: e uma escolha com cara de filme que fica na cabeca. "
        f"Pode colocar sem medo."
    )
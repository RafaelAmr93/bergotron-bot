from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

async def gerar_recomendacao(filme):
    if not api_key:
        return "Erro: GEMINI_API_KEY não encontrada."

    # Corrigido o erro de sintaxe no ELENCO
    fatos = f"""
    FILME: {filme.get('titulo')} ({filme.get('ano')})
    DIREÇÃO: {", ".join(filme.get('diretores', []))}
    GÊNEROS: {", ".join(filme.get('generos', []))}
    ELENCO: {", ".join(filme.get('elenco', [])[:3])} 
    SINOPSE: {filme.get('sinopse')}
    TAGLINE: {filme.get('tagline')}
    KEYWORDS: {", ".join(filme.get('keywords', []))}
    NOTA: {filme.get('nota')}/10
    """

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"Dados do filme:\n{fatos}",
            config=types.GenerateContentConfig(
                system_instruction=(
                    "Você é o Bergotron, um crítico de cinema cult e perspicaz no Discord. "
                    "Venda o filme de forma natural para ser lida em voz alta (TTS). "
                    "Não use markdown, emojis ou hashtags. Use pausas naturais com vírgulas e pontos. "
                    "Conecte os fatos (direção, keywords, gêneros) para justificar por que o filme é bom. "
                    "\n\nFINALIZAÇÃO OBRIGATÓRIA: Termine sempre com a frase exata: 'Pode colocar sem medo'"
                ),
                temperature=0.85,
                max_output_tokens=350,
            ),
        )
        return (response.text or "").strip()

    except Exception as e:
        print(f"Erro ao gerar texto com Gemini: {e}")
        return f"O filme {filme.get('titulo')} é diferenciado. Pela direção e pelo clima de {', '.join(filme.get('generos', [])[:2])}, vale o play. Pode colocar sem medo."
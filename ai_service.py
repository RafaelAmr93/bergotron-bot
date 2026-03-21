import google.generativeai as genai
import os

def configurar_ia():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Erro: GEMINI_API_KEY nao encontrada.")
        return False
    genai.configure(api_key=api_key)
    return True

async def gerar_recomendacao(titulo, sinopse):
    if not configurar_ia():
        return "Erro na configuracao da IA."

    try:
        # Usando o modelo flash que e muito rapido para textos curtos
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Aja como um critico de cinema em um canal do Discord. 
        Voce vai recomendar o filme '{titulo}'.
        A sinopse oficial e: {sinopse}
        
        Escreva um paragrafo curto, empolgante e direto ao ponto em portugues.
        O texto deve ser feito para ser lido em voz alta por um bot (Text-to-Speech), 
        entao nao use emojis, aspas complexas, hashtags ou formatacoes. Seja natural e fale como um humano conversando.
        """
        
        # O discord.py e assincrono, entao usamos a versao async da chamada do Gemini
        response = await model.generate_content_async(prompt)
        return response.text.strip()
        
    except Exception as e:
        print(f"Erro ao gerar texto com Gemini: {e}")
        return "Infelizmente, a minha mente deu um branco e nao consegui pensar em uma recomendacao agora."
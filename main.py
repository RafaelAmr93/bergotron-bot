import discord
from discord.ext import commands
import os
import asyncio
from gtts import gTTS
from dotenv import load_dotenv

# Importando os modulos que criamos
import db
import tmdb_service
import ai_service

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot online e conectado como {bot.user}')

@bot.command(name='recomende')
async def recomende(ctx):
    if not ctx.message.author.voice:
        await ctx.send("Voce precisa estar em um canal de voz para eu falar a recomendacao!")
        return

    canal_de_voz = ctx.message.author.voice.channel
    mensagem_status = await ctx.send("Entrando no canal e pensando em um filme...")

    try:
        # 1. Conecta no canal de voz
        vc = await canal_de_voz.connect()

        # 2. Sorteia um ID do SQLite
        filme_id = db.get_filme_aleatorio()
        if not filme_id:
            await ctx.send("Nenhum filme cadastrado no banco de dados.")
            await vc.disconnect()
            return

        # 3. Busca detalhes no TMDB
        dados_filme = await tmdb_service.buscar_filme(filme_id)
        if not dados_filme:
            await ctx.send("Erro ao buscar detalhes do filme na API.")
            await vc.disconnect()
            return

        # 4. Pede para o Gemini gerar o texto da recomendacao
        await mensagem_status.edit(content=f"Preparando a critica de '{dados_filme['titulo']}'...")
        texto_recomendacao = await ai_service.gerar_recomendacao(
            dados_filme['titulo'], 
            dados_filme['sinopse']
        )

        # 5. Converte o texto da IA em audio usando gTTS
        nome_arquivo = f"recomendacao_{ctx.message.author.id}.mp3"
        tts = gTTS(text=texto_recomendacao, lang='pt', tld='com.br')
        tts.save(nome_arquivo)

        # 6. Toca o audio no Discord usando FFmpeg
        await mensagem_status.edit(content=f"Falando sobre: {dados_filme['titulo']}!")
        vc.play(discord.FFmpegPCMAudio(nome_arquivo))

        # Espera o bot terminar de falar antes de desconectar
        while vc.is_playing():
            await asyncio.sleep(1)

        # 7. Desconecta e limpa o arquivo de audio
        await vc.disconnect()
        
        if os.path.exists(nome_arquivo):
            os.remove(nome_arquivo)

        await mensagem_status.edit(content="Recomendacao finalizada!")

    except Exception as e:
        await ctx.send(f"Ocorreu um erro durante a recomendacao: {e}")
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token)
    else:
        print("Erro: DISCORD_TOKEN nao encontrado no .env")
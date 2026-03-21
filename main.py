import discord
from discord.ext import commands
import os
import asyncio
import edge_tts
from dotenv import load_dotenv
import re
import db
import tmdb_service
import ai_service

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

async def gerar_audio(texto: str, arquivo: str):
    communicate = edge_tts.Communicate(
        text=texto,
        voice="pt-BR-AntonioNeural"
    )
    await communicate.save(arquivo)

def extrair_tmdb_id(link: str):
    match = re.search(r"/movie/(\d+)", link)
    if match:
        return int(match.group(1))
    return None

@bot.event
async def on_ready():
    db.inicializar_banco()
    print(f'Bot online e conectado como {bot.user}')


@bot.command(name='recomende')
@commands.cooldown(1, 30, commands.BucketType.user)
async def recomende(ctx):
    if not ctx.author.voice:
        await ctx.send("Voce precisa estar em um canal de voz para eu falar a recomendacao!")
        return

    canal_de_voz = ctx.author.voice.channel
    mensagem_status = await ctx.send("Entrando no canal e pensando em um filme...")

    vc = None
    nome_arquivo = None

    try:
        vc = ctx.voice_client
        if vc is None:
            vc = await canal_de_voz.connect()
        elif vc.channel != canal_de_voz:
            await vc.move_to(canal_de_voz)

        filme_id = db.get_filme_aleatorio()
        if not filme_id:
            await mensagem_status.edit(content="Nenhum filme cadastrado no banco de dados.")
            return

        dados_filme = await tmdb_service.buscar_filme(filme_id)
        if not dados_filme:
            await mensagem_status.edit(content="Erro ao buscar detalhes do filme na API.")
            return

        await mensagem_status.edit(
            content=f"Preparando a critica de '{dados_filme['titulo']}'..."
        )

        texto_recomendacao = await ai_service.gerar_recomendacao(dados_filme)

        nome_arquivo = f"recomendacao_{ctx.author.id}.mp3"

        await gerar_audio(texto_recomendacao, nome_arquivo)

        await mensagem_status.edit(content=f"Falando sobre: {dados_filme['titulo']}!")
        vc.play(discord.FFmpegOpusAudio(nome_arquivo))

        while vc.is_playing():
            await asyncio.sleep(1)

        await mensagem_status.edit(
            content=f"Recomendacao finalizada! Vou continuar no canal {vc.channel.name}."
        )

    except Exception as e:
        await mensagem_status.edit(content=f"Ocorreu um erro durante a recomendacao: {e}")

    finally:
        if nome_arquivo and os.path.exists(nome_arquivo):
            os.remove(nome_arquivo)

@bot.command(name="entrar")
async def entrar(ctx):
    if not ctx.author.voice:
        await ctx.send("Entre em um canal de voz primeiro.")
        return

    canal = ctx.author.voice.channel
    vc = ctx.voice_client

    if vc is None:
        await canal.connect()
        await ctx.send(f"Entrei em {canal.name}.")
    elif vc.channel != canal:
        await vc.move_to(canal)
        await ctx.send(f"Fui para {canal.name}.")
    else:
        await ctx.send(f"Ja estou em {canal.name}.")


@bot.command(name="sair")
async def sair(ctx):
    if ctx.voice_client and ctx.voice_client.is_connected():
        canal = ctx.voice_client.channel.name
        await ctx.voice_client.disconnect()
        await ctx.send(f"Saindo de {canal}.")
    else:
        await ctx.send("Nao estou em canal de voz.")

@recomende.error
async def recomende_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        tempo_restante = round(error.retry_after, 1)
        await ctx.send(
            f"⏳ Calma lá! O Bergotron precisa de um respiro. "
            f"Tente de novo em {tempo_restante} segundos."
        )

@bot.command(name="adicionar")
@commands.cooldown(1, 10, commands.BucketType.user)
async def adicionar(ctx, *, link: str = None):
    if not link:
        await ctx.send(
            "Mande o comando assim:\n"
            "!adicionar https://www.themoviedb.org/movie/12345-nome-do-filme"
        )
        return

    tmdb_id = extrair_tmdb_id(link)

    if not tmdb_id:
        await ctx.send(
            "Nao consegui identificar o ID do filme nesse link.\n"
            "Use um link do TMDB no formato:\n"
            "https://www.themoviedb.org/movie/12345-nome-do-filme"
        )
        return

    try:
        dados_filme = await tmdb_service.buscar_filme(tmdb_id)
    except Exception as e:
        await ctx.send(f"Erro ao consultar o TMDB: {e}")
        return

    if not dados_filme:
        await ctx.send("Nao consegui validar esse filme no TMDB. Confira o link.")
        return

    try:
        inserido = db.adicionar_filme(tmdb_id)
    except Exception as e:
        await ctx.send(f"Erro ao salvar no banco: {e}")
        return

    if inserido:
        await ctx.send(
            f"Filme adicionado com sucesso: {dados_filme['titulo']} "
            f"(TMDB ID: {tmdb_id})"
        )
    else:
        await ctx.send(
            f"Esse filme ja estava cadastrado: {dados_filme['titulo']} "
            f"(TMDB ID: {tmdb_id})"
        )

@bot.command(name="bergotron")
async def bergotron(ctx):
    mensagem = (
        "Eu sou o Bergotron, seu oraculo cinematografico de confiança.\n\n"
        "Minha missao e simples: entrar no canal de voz, puxar um filme do banco e vender a ideia "
        "como se fosse uma recomendacao feita por um amigo cinéfilo.\n\n"
        "Comandos:\n"
        "`!bergotron` - mostra esta ajuda.\n"
        "`!entrar` - entro no canal de voz onde voce estiver.\n"
        "`!sair` - saio do canal de voz.\n"
        "`!recomende` - escolho um filme aleatorio e faco a recomendacao em voz alta.\n"
        "`!adicionar <link do TMDB>` - adiciona um filme ao banco usando o link do TMDB.\n\n"
        "Exemplo de cadastro:\n"
        "`!adicionar https://www.themoviedb.org/movie/680-pulp-fiction`"
    )
    await ctx.send(mensagem)

@adicionar.error
async def adicionar_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        tempo_restante = round(error.retry_after, 1)
        await ctx.send(f"Tente de novo em {tempo_restante} segundos.")
        return

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "Use assim:\n"
            "!adicionar https://www.themoviedb.org/movie/12345-nome-do-filme"
        )
        return

    await ctx.send(f"Erro no comando adicionar: {error}")


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Erro: DISCORD_TOKEN nao encontrado no .env")
import os
import asyncio
import discord
import edge_tts
from discord.ext import commands
from dotenv import load_dotenv

import db
import tmdb_service
import ai_service

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def gerar_audio(texto: str, arquivo: str):
    communicate = edge_tts.Communicate(
        text=texto,
        voice="pt-BR-AntonioNeural"
    )
    await communicate.save(arquivo)


def sanitizar_busca_filme(texto: str) -> str:
    texto = (texto or "").strip()

    if not texto:
        raise ValueError("Informe o nome do filme.")

    if len(texto) > 120:
        raise ValueError("Nome do filme muito grande. Tente algo mais curto.")

    # Remove caracteres de controle
    texto = "".join(ch for ch in texto if ch.isprintable())

    # Normaliza espaços
    texto = " ".join(texto.split())

    # Defesa leve contra entradas claramente maliciosas
    padroes_suspeitos = [";", "--", "/*", "*/", "\x00"]
    if any(p in texto for p in padroes_suspeitos):
        raise ValueError("Entrada invalida.")

    return texto


@bot.event
async def on_ready():
    db.inicializar_banco()
    print(f"Bot online e conectado como {bot.user}")


@bot.command(name="recomende")
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

        dados_filme = await tmdb_service.buscar_filme(int(filme_id))
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
async def adicionar(ctx, *, entrada: str = None):
    if not entrada:
        await ctx.send(
            "Use assim:\n"
            "`!adicionar Nome do Filme`\n"
            "Ou varios separados por `;`\n\n"
            "Exemplos:\n"
            "`!adicionar Pulp Fiction`\n"
            "`!adicionar Batman Begins 2005; Batman: O Cavaleiro das Trevas 2008; Batman: O Cavaleiro das Trevas Ressurge 2012`"
        )
        return

    filmes = separar_entradas_filmes(entrada)

    if not filmes:
        await ctx.send("Informe pelo menos um filme.")
        return

    if len(filmes) > 5:
        await ctx.send("Voce pode adicionar no maximo 5 filmes por comando.")
        return

    resultados = []
    for filme in filmes:
        msg = await processar_adicao_filme(filme)
        resultados.append(msg)

    resposta = "\n\n".join(resultados)

    if len(resposta) > 1900:
        resposta = resposta[:1900] + "\n..."

    await ctx.send(resposta)
    return


@bot.command(name="bergotron")
async def bergotron(ctx):
    mensagem = (
        "Eu sou o Bergotron, seu oraculo cinematografico de confianca.\n\n"
        "Comandos:\n"
        "`!bergotron` - mostra esta ajuda.\n"
        "`!entrar` - entro no canal de voz onde voce estiver.\n"
        "`!sair` - saio do canal de voz.\n"
        "`!recomende` - escolho um filme aleatorio e faco a recomendacao em voz alta.\n"
        "`!adicionar <nome do filme>` - adiciona um filme ao banco usando o nome.\n"
        "`!adicionar filme1; filme2; filme3` - adiciona varios filmes de uma vez.\n\n"
        "Exemplos:\n"
        "`!adicionar Pulp Fiction`\n"
        "`!adicionar O Segredo de Brokeback Mountain 2005`\n"
        "`!adicionar Batman Begins 2005; Batman: O Cavaleiro das Trevas 2008; Batman: O Cavaleiro das Trevas Ressurge 2012`"
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
            "`!adicionar Nome do Filme`"
        )
        return

    await ctx.send(f"Erro no comando adicionar: {error}")

import re

def separar_entradas_filmes(texto: str) -> list[str]:
    texto = (texto or "").strip()

    if not texto:
        return []

    # Preferencia por ponto e virgula, que é mais seguro
    if ";" in texto:
        partes = texto.split(";")
    else:
        # aceita virgula como conveniencia
        partes = texto.split(",")

    filmes = []
    for parte in partes:
        item = " ".join(parte.split()).strip()
        if item:
            filmes.append(item)

    return filmes

async def processar_adicao_filme(nome_filme: str) -> str:
    try:
        nome_filme = sanitizar_busca_filme(nome_filme)
    except ValueError as e:
        return f"❌ `{nome_filme}` -> {e}"

    try:
        resultado = await tmdb_service.buscar_filme_por_nome(nome_filme)
    except Exception as e:
        return f"Erro ao consultar o TMDB para `{nome_filme}`: {e}"

    status = resultado.get("status")

    if status == "erro":
        return f"Nao consegui consultar o TMDB para `{nome_filme}`."

    if status == "nenhum":
        return (
            f"Nao encontrei resultados para `{nome_filme}`. "
            "Tente usar o titulo original ou informar o ano.\n"
            "Exemplo:\n"
            "`!adicionar Brokeback Mountain 2005`\n"
            "Ou para multiplas adicoes:\n"
            "`!adicionar Brokeback Mountain 2005; Batman: O Cavaleiro das Trevas 2008`"
        )

    if status == "multiplo":
        opcoes = resultado.get("resultados", [])
        linhas = [
            f"{item['titulo']} ({item['ano'] or 'ano desconhecido'})"
            for item in opcoes
        ]

        return (
            f"Encontrei varios resultados para `{nome_filme}`:\n\n"
            + "\n".join(linhas)
            + "\n\nRefaça o comando com um nome mais especifico, de preferencia com ano.\n"
            "Exemplos:\n"
            "`!adicionar Batman Begins 2005`\n"
            "`!adicionar The Batman 2022; Batman Begins 2005`"
        )

    if status != "ok":
        return f"Nao consegui processar a busca para `{nome_filme}`."

    filme = resultado.get("filme")
    if not filme:
        return f"Encontrei `{nome_filme}`, mas falhei ao buscar os detalhes."

    try:
        tmdb_id = int(filme["id"])
        inserido = db.adicionar_filme(tmdb_id)
    except Exception as e:
        return f"Erro ao salvar `{nome_filme}` no banco: {e}"

    if inserido:
        return f"✅ {filme['titulo']} ({filme['ano']}) adicionado."
    return f"ℹ️ {filme['titulo']} ({filme['ano']}) ja estava cadastrado."

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Erro: DISCORD_TOKEN nao encontrado no .env")
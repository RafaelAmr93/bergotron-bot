import os
import re
import asyncio
import discord
import edge_tts
from discord.ext import commands
from dotenv import load_dotenv
import random
import aiohttp

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

    texto = "".join(ch for ch in texto if ch.isprintable())
    texto = " ".join(texto.split())

    padroes_suspeitos = [";", "--", "/*", "*/", "\x00"]
    if any(p in texto for p in padroes_suspeitos):
        raise ValueError("Entrada invalida.")

    return texto


def separar_entradas_filmes(texto: str) -> list[str]:
    texto = (texto or "").strip()

    if not texto:
        return []

    # Aceita tanto ponto e vírgula quanto vírgula
    if ";" in texto:
        partes = texto.split(";")
    else:
        partes = texto.split(",")

    filmes = []
    for parte in partes:
        item = " ".join(parte.split()).strip()
        if item:
            filmes.append(item)

    return filmes


async def conectar_no_canal_do_usuario(ctx):
    if not ctx.author.voice:
        await ctx.send("Voce precisa estar em um canal de voz para eu falar a recomendacao!")
        return None

    canal_de_voz = ctx.author.voice.channel
    vc = ctx.voice_client

    if vc is None:
        vc = await canal_de_voz.connect()
    elif vc.channel != canal_de_voz:
        await vc.move_to(canal_de_voz)

    return vc


async def tocar_recomendacao(ctx, dados_filme: dict, mensagem_inicial: str):
    mensagem_status = await ctx.send(mensagem_inicial)
    nome_arquivo = None

    try:
        await mensagem_status.edit(
            content=f"Preparando a critica de '{dados_filme['titulo']}'..."
        )

        # Gera o texto com o Ollama/Fallback
        texto_recomendacao = await ai_service.gerar_recomendacao(dados_filme)
        if not texto_recomendacao or not texto_recomendacao.strip():
            await mensagem_status.edit(content="O modelo não gerou texto para esse filme.")
            return

        # Gera o áudio com Edge TTS
        nome_arquivo = f"recomendacao_{ctx.author.id}.mp3"
        await gerar_audio(texto_recomendacao, nome_arquivo)

        # Conecta no canal de voz
        vc = await conectar_no_canal_do_usuario(ctx)
        if vc is None:
            return

        # Toca o áudio
        await mensagem_status.edit(content=f"Falando sobre: {dados_filme['titulo']}!")
        vc.play(discord.FFmpegOpusAudio(nome_arquivo))

        # Espera o áudio terminar de tocar
        while vc.is_playing():
            await asyncio.sleep(1)

        await mensagem_status.edit(
            content=f"Recomendacao finalizada! Vou continuar no canal {vc.channel.name}."
        )

    except Exception as e:
        await mensagem_status.edit(content=f"Ocorreu um erro durante a recomendacao: {e}")

    finally:
        # Limpa o arquivo mp3 gerado
        if nome_arquivo and os.path.exists(nome_arquivo):
            os.remove(nome_arquivo)


@bot.event
async def on_ready():
    print(f"Bot online e conectado como {bot.user}")


@bot.command(name="bergotron")
async def bergotron(ctx):
    mensagem = (
        "Eu sou o Bergotron, seu oraculo cinematografico de confianca.\n\n"
        "Comandos:\n"
        "`!bergotron` - mostra esta ajuda.\n"
        "`!entrar` - entro no canal de voz onde voce estiver.\n"
        "`!sair` - saio do canal de voz.\n"
        "`!recomendar <filme>` - busco o filme e faco a recomendacao em voz alta.\n"
        "`!recomendar <filme1>, <filme2>` - sorteio um dos filmes e faco a recomendacao.\n\n"
        "Exemplos:\n"
        "`!recomendar Pulp Fiction`\n"
        "`!recomendar Batman Begins 2005, The Batman 2022, Coringa`\n"
    )
    await ctx.send(mensagem)


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


@bot.command(name="recomendar")
@commands.cooldown(1, 20, commands.BucketType.user)
async def recomendar(ctx, *, entrada: str = None):
    if not entrada:
        await ctx.send(
            "Me diga o que recomendar!\n"
            "Exemplo 1: `!recomendar Pulp Fiction`\n"
            "Exemplo 2: `!recomendar Matrix, Shrek, Gladiador`"
        )
        return

    filmes = separar_entradas_filmes(entrada)
    
    if not filmes:
        await ctx.send("Nao consegui entender os nomes dos filmes.")
        return

# Logica do sorteio: se houver mais de um, escolhe um aleatoriamente
    if len(filmes) > 1:
        filme_escolhido = random.choice(filmes)
        # Manda uma mensagem definitiva que vai ficar no histórico do chat
        await ctx.send(f"🎲 **Roleta girando...** Opções na mesa, mas o escolhido foi: `{filme_escolhido}`!")
        # Cria a mensagem temporária para o feedback visual
        mensagem_status = await ctx.send("Buscando no TMDB...")
    else:
        filme_escolhido = filmes[0]
        mensagem_status = await ctx.send(f"Buscando `{filme_escolhido}` no TMDB...")

    try:
        nome_sanitizado = sanitizar_busca_filme(filme_escolhido)
        resultado = await tmdb_service.buscar_filme_por_nome(nome_sanitizado)
    except ValueError as e:
        await mensagem_status.edit(content=str(e))
        return
    except Exception as e:
        await mensagem_status.edit(content=f"Erro ao consultar o TMDB: {e}")
        return

    status = resultado.get("status")

    if status == "erro":
        await mensagem_status.edit(content=f"Nao consegui consultar o TMDB para `{filme_escolhido}`.")
        return

    if status == "nenhum":
        await mensagem_status.edit(content=f"Nao encontrei resultados para `{filme_escolhido}`. Tente colocar o ano junto (Ex: Batman 1989).")
        return

    if status == "multiplo":
        opcoes = resultado.get("resultados", [])
        linhas = [
            f"{item['titulo']} ({item['ano'] or 'ano desconhecido'})"
            for item in opcoes[:5] # Mostra só os 5 primeiros para não poluir
        ]

        await mensagem_status.edit(
            content=(
                f"Encontrei varios resultados para `{filme_escolhido}`:\n\n"
                + "\n".join(linhas)
                + "\n\nRefaça o comando com um nome mais especifico, de preferencia com ano."
            )
        )
        return

    if status != "ok":
        await mensagem_status.edit(content=f"Nao consegui processar a busca para `{filme_escolhido}`.")
        return

    filme = resultado.get("filme")
    if not filme:
        await mensagem_status.edit(content=f"Encontrei `{filme_escolhido}`, mas falhei ao buscar os detalhes.")
        return

    try:
        dados_filme = await tmdb_service.buscar_filme(int(filme["id"]))
    except Exception as e:
        await mensagem_status.edit(content=f"Erro ao buscar os detalhes do filme: {e}")
        return

    if not dados_filme:
        await mensagem_status.edit(content=f"Falhei ao buscar os detalhes finais de `{filme_escolhido}`.")
        return

    try:
        await mensagem_status.delete()
    except Exception:
        pass

    await tocar_recomendacao(
        ctx,
        dados_filme,
        f"🎬 Encontrei `{dados_filme['titulo']}`. Preparando a recomendacao..."
    )


@recomendar.error
async def recomendar_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        tempo_restante = round(error.retry_after, 1)
        await ctx.send(f"⏳ Calma lá! O Bergotron precisa de um respiro. Tente de novo em {tempo_restante} segundos.")
        return

    await ctx.send(f"Erro no comando recomendar: {error}")


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Erro: DISCORD_TOKEN nao encontrado no .env")
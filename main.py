import os
import re
import discord
import asyncio
from discord import Intents
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz  # timezone handling

with open("token.txt", "r") as file:
    TOKEN = file.read().strip()

games_played = {}
daily_rating_change = {}
wins = {}
losses = {}

def extract_name_rating_line(line):
    name_match = re.match(r"(.+?):", line)
    rating_match = re.search(r"(\d+)\s*→\s*(\d+)\s*\(([-+]?\d+)\)", line)
    if name_match and rating_match:
        name = name_match.group(1).strip()
        delta = int(rating_match.group(3))
        return name, delta
    return None, None

intents = Intents.default()
intents.message_content = True
intents.guilds = True

bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        await bot.sync_commands()
        print("✅ Synced slash commands.")
    except Exception as e:
        print(f"⚠️ Error syncing commands: {e}")
    bot.loop.create_task(reset_leaderboard_at_midnight_cet())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Process embeds
    for embed in message.embeds:
        if embed.description and "→" in embed.description:
            for line in embed.description.splitlines():
                name, rating_delta = extract_name_rating_line(line)
                if name:
                    games_played[name] = games_played.get(name, 0) + 1
                    daily_rating_change[name] = daily_rating_change.get(name, 0) + rating_delta
                    if rating_delta > 0:
                        wins[name] = wins.get(name, 0) + 1
                    elif rating_delta < 0:
                        losses[name] = losses.get(name, 0) + 1
                    print(f"📈 {name}: +1 game, Δ {rating_delta} rating")

    # Also check plain message content just in case
    if message.content and "→" in message.content:
        for line in message.content.splitlines():
            name, rating_delta = extract_name_rating_line(line)
            if name:
                games_played[name] = games_played.get(name, 0) + 1
                daily_rating_change[name] = daily_rating_change.get(name, 0) + rating_delta
                if rating_delta > 0:
                    wins[name] = wins.get(name, 0) + 1
                elif rating_delta < 0:
                    losses[name] = losses.get(name, 0) + 1
                print(f"📈 {name}: +1 game, Δ {rating_delta} rating")

def create_leaderboard_embed(title, sorted_list, stat_name, stat_getter, stat_suffix=""):
    embed = discord.Embed(title=title, color=discord.Color.gold())
    text = ""
    for rank, (name, _) in enumerate(sorted_list, start=1):
        stat_value = stat_getter(name)
        text += f"**{rank}. {name}** — {stat_value}{stat_suffix}\n"
    embed.description = text
    embed.set_footer(text=f"Tracked by {bot.user.name}")
    return embed

@bot.slash_command(name="leaderboard", description="Show combined leaderboard sorted by games played")
async def leaderboard(ctx: discord.ApplicationContext):
    if not games_played:
        await ctx.respond("No games tracked yet.")
        return
    # Sort by games played desc
    sorted_players = sorted(games_played.items(), key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title="📊 Combined Leaderboard (sorted by games played)",
        color=discord.Color.gold()
    )
    leaderboard_text = ""
    for rank, (name, game_count) in enumerate(sorted_players, start=1):
        w = wins.get(name, 0)
        l = losses.get(name, 0)
        rating = daily_rating_change.get(name, 0)
        rating_sign = f"+{rating}" if rating > 0 else str(rating)
        leaderboard_text += (
            f"**{rank}. {name}** — Games: {game_count}, Wins: {w}, Losses: {l}, Rating: {rating_sign}\n"
        )
    embed.description = leaderboard_text
    embed.set_footer(text=f"Tracked by {bot.user.name}")
    await ctx.respond(embed=embed)

@bot.slash_command(name="games_leaderboard", description="Show leaderboard sorted by games played")
async def games_leaderboard(ctx: discord.ApplicationContext):
    if not games_played:
        await ctx.respond("No games tracked yet.")
        return
    sorted_players = sorted(games_played.items(), key=lambda x: x[1], reverse=True)
    embed = create_leaderboard_embed(
        "🏆 Games Played Leaderboard",
        sorted_players,
        "Games Played",
        lambda name: games_played.get(name, 0),
        " games"
    )
    await ctx.respond(embed=embed)

@bot.slash_command(name="wins_leaderboard", description="Show leaderboard sorted by wins")
async def wins_leaderboard(ctx: discord.ApplicationContext):
    if not wins:
        await ctx.respond("No wins tracked yet.")
        return
    sorted_players = sorted(wins.items(), key=lambda x: x[1], reverse=True)
    embed = create_leaderboard_embed(
        "🎉 Wins Leaderboard",
        sorted_players,
        "Wins",
        lambda name: wins.get(name, 0),
        " wins"
    )
    await ctx.respond(embed=embed)

@bot.slash_command(name="losses_leaderboard", description="Show leaderboard sorted by losses")
async def losses_leaderboard(ctx: discord.ApplicationContext):
    if not losses:
        await ctx.respond("No losses tracked yet.")
        return
    sorted_players = sorted(losses.items(), key=lambda x: x[1], reverse=True)
    embed = create_leaderboard_embed(
        "😞 Losses Leaderboard",
        sorted_players,
        "Losses",
        lambda name: losses.get(name, 0),
        " losses"
    )
    await ctx.respond(embed=embed)

@bot.slash_command(name="rating_leaderboard", description="Show leaderboard sorted by rating gained")
async def rating_leaderboard(ctx: discord.ApplicationContext):
    if not daily_rating_change:
        await ctx.respond("No rating changes tracked yet.")
        return
    sorted_players = sorted(daily_rating_change.items(), key=lambda x: x[1], reverse=True)
    embed = create_leaderboard_embed(
        "⭐ Rating Change Leaderboard",
        sorted_players,
        "Rating Change",
        lambda name: daily_rating_change.get(name, 0),
        " rating"
    )
    await ctx.respond(embed=embed)

async def reset_leaderboard_at_midnight_cet():
    cet = pytz.timezone('Europe/Paris')
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now(cet)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (next_midnight - now).total_seconds()
        print(f"⏳ Waiting {wait_seconds:.2f}s until next CET midnight reset.")
        await asyncio.sleep(wait_seconds)
        games_played.clear()
        daily_rating_change.clear()
        wins.clear()
        losses.clear()
        print("🔄 Leaderboard has been reset at CET midnight.")

bot.run(TOKEN)

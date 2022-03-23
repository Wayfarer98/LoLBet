import os
from discord.ext import commands
from dotenv import load_dotenv
from scrape_data import ScrapeData

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

scrape_class = ScrapeData()

bot = commands.Bot(command_prefix='!')

#TODO: Make a better help message

@bot.command(name="test", help="Testing help")
async def schedule(ctx):
    await ctx.send('Twerks!')

@bot.command(name='update', help="Update the current instance of lolesports.com")
async def update(ctx):
    scrape_class.update()
    await ctx.send('Updated.')

@bot.command(name='live', help='A list of currently live matches')
async def live(ctx):
    live_lst = await scrape_class.live_now()
    if not live_lst:
        await ctx.send('No live games. If you think this is wrong, run !update and try again.')
        return
    for game in live_lst:
        await ctx.send(f"{game['team1']['tricode']} vs. {game['team2']['tricode']} plays {game['number']} in {game['league']} {game['round']}")
    return

@bot.command(name='upcoming', help='A list of games within the next 10 days. Add a league as argument to see only those specific games')
async def upcomming(ctx, league='all'):
    upcomming_games = await scrape_class.upcomming_games(league=league.upper())

    if isinstance(upcomming_games, str):
        await ctx.send(upcomming_games)
        return

    send_string = f""
    for game_date in upcomming_games:
        if not any(game_date['games']):
            continue
        send_string += f"{game_date['date']}:\n"
        for game in game_date['games']:
            if not game:
                continue
            send_string += f"\t{game['league']}\n"
            send_string += f"\t{game['time']} -> {game['team1']['tricode']} vs. {game['team2']['tricode']}\n"
        send_string += '\n'
    
    if not send_string:
        await ctx.send('There are no games within the next 10 days to show.')
    else:
        await ctx.send(send_string)

bot.run(TOKEN)
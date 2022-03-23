"""
Module used to scrape the lolesports.com website for schedules etc.
"""

import datetime
import time
from bs4 import BeautifulSoup
from selenium import webdriver


class ScrapeData:
    """
    Class for storing and scraping the HTML and data of the LoL Esports
    source pages
    """

    def __init__(self):
        """Initializer just calls the update function"""
        self.update()
        self.supported_leagues = ('LEC', 'LCS', 'LCK', 'LPL', 'MSI', 'WORLDS', 'ALL')

    def update(self):
        """Update the HTML source of the appropriate websites"""
        # Get the HTML for the schedule
        browser = webdriver.Firefox() # Opens a browser window
        browser.get(
            "https://lolesports.com/schedule?leagues=lec,lcs,lck,lpl,msi,worlds")
        time.sleep(1) # Sleep 1 sec to make sure that the page is fully loaded

        self.schedule_source = browser.page_source
        browser.close()
        self.schedule_soup = BeautifulSoup(self.schedule_source, 'html.parser')

    async def live_now(self):
        """Get a list of games that are currently live"""
        # sourcery skip: inline-immediately-returned-variable
        # Find all games that are currently live. Discard the "going live" infos
        live_parents = self.schedule_soup.find_all('a', {'class': 'live'})

        # Extract information from games that are currently live
        games = []
        for live_parent in live_parents:
            if game := ScrapeData._extract_game(live_parent.parent, live=True):
                games.append(game)

        return games

    async def upcomming_games(self, league='all'):
        """Get a list of dates and games on those dates if they are within the next 10 days"""
        # sourcery skip: inline-immediately-returned-variable
        dates_parents = self.schedule_soup.find_all('div', {'class': 'date'})
        if league not in self.supported_leagues:
            return f"Invalid league argument. Expected one of {self.supported_leagues}, got {league}"
        # Collect weekday and monthday in a tuple if the date is within the next 10 days of today
        dates = [
            (date.find('span', {'class': 'weekday'}),
             date.find('span', {'class': 'monthday'}))
            for date in dates_parents
            if ScrapeData._within_10_days(date.find('span', {'class': 'monthday'}).get_text())
        ]

        # Make a dict with a date string and a list of all the games on the current date
        # Uses the dates found above, so all dates are within the next 10 days
        games_dates = [
            {
                'date': f"{weekday.get_text()} {monthday.get_text()}",
                'games': [
                    ScrapeData._extract_game(game, league, past=False, live=False)
                    for game in list(ScrapeData._while_match_generator(monthday.parent.parent))
                ],
            }
            for weekday, monthday in dates
        ]

        return games_dates

    @classmethod
    def _within_10_days(cls, date):
        # Check if date is within 10 days.
        # Format of input date string is "%d %B" which is "day(int) month(fully written)"
        today = datetime.datetime.now()
        # Create a datetime object with the input date and replace the year with current year
        # TODO: Fix issues when current date is within 10 days of new year
        game_date = datetime.datetime.strptime(date, "%d %B")
        game_date = datetime.datetime.replace(game_date, year=today.year)
        # Difference of the two dates in days
        diff = (game_date - today).days
        if 0 <= diff <= 10:
            return True
        return False

    @classmethod
    def _while_match_generator(cls, soup):
        # EventMatch and EventDate divs are siblings.
        # Go through all siblings that are EventMatches
        # These will be matches played on the previous EventDate date.
        sibling = soup.find_next_sibling()
        while sibling['class'][0] == 'EventMatch':
            # Generator yields the result, see https://www.geeksforgeeks.org/python-yield-keyword/
            yield sibling
            #update the sibling before next loop iteration
            sibling = sibling.find_next_sibling()

    @classmethod
    def _extract_game(cls, event_soup, league='all', past=False, live=False):
        """
        Extract the game data from a soup with EventMatch class
        
        Live games has:
            team1
            team2
            league
            round
            number
            finished

        Finished games has
            team1
            team2
            league
            winner
            score
            time
            strategy
            finished
        """

        # always use uppercase letters
        league = league.upper()
        # Make sure the event_soup is an instance and not EventShow class
        # Since EventShows are also displayed like a live game
        # In the wrong cases, return empty dict
        if not event_soup or event_soup['class'][0] == 'EventShow':
            return {}

        # Get the league of the game played
        game_league = event_soup.find('div', {'class': 'league'}).find(
            ['div', 'span'], {'class': 'name'}).get_text()

        # If the league is not matching the games league, return empty dict
        if league not in ('ALL', game_league):
            return {}

        # Extract all generic data that a game always has
        game = {
            'finished': past,
            'team1': ScrapeData._extract_team(event_soup.find('div', {'class': 'team1'})),
            'team2': ScrapeData._extract_team(event_soup.find('div', {'class': 'team2'})),
            'league': game_league
        }

        # If the game is finished, we also get the winner and score of the game
        if game['finished']:
            winner = event_soup.find('div', {'class': 'teams'})['class'][1][7:]
            game['winner'] = game[winner]['name']
            game['score'] = event_soup.find('div', {'class': 'score'}).get_text()

        # If the game is not live, then they have a game time and strategy
        # Game time is the time of day the game is played
        # Strategy is the kind of games, like Bo1, Bo3 or Bo5
        if not live:
            game['time'] = event_soup.find('div', {'class': 'time'}).get_text()[:2]
            game['time'] += ":" + event_soup.find('div', {'class': 'time'}).get_text()[2:4]

            game['strategy'] = event_soup.find('div', {'class': 'league'})
            game['strategy'] = game['strategy'].find('div', {'class': 'strategy'}).get_text()
        # If the game is live, then it has a round and a number
        # Round is the round in the league, like week 9 or playoffs or finals
        # Number is the game they play, like game 3, if it is a Bo3
        else:
            game['round'] = event_soup.find('span', {'class': 'round'}).get_text()
            game['number'] = event_soup.find('span', {'class': 'game-number'}).get_text()

        return game

    @classmethod
    def _extract_team(cls, team_soup):
        # Extract the team data as a dict
        team = {
            'img': team_soup.find('img')['src'],
            'name': team_soup.find('span', {'class': 'name'}).get_text(),
            'tricode': team_soup.find('span', {'class': 'tricode'}).get_text()
        }
        # If there is a W/L, include it
        if w_l := team_soup.find('div', {'class': 'winloss'}):
            team['W/L'] = w_l.get_text()

        return team

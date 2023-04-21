import json
import sys

from bs4 import BeautifulSoup

from ikabot import config
from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import enter
from ikabot.helpers.pedirInfo import chooseCity, getIdsOfCities
from rich.table import Table
from rich.console import Console


# Receives html of the city troops
def parse_units_from_html(html):
    soup = BeautifulSoup(html, features="html.parser")

    divs = soup.find_all('div', id=True)

    units = {}
    ships = {}

    for i in divs:
        if i["id"] == "tabUnits":
            unit_names = i.find_all('tr')[0].find_all('div', class_='tooltip')
            counts = i.find_all('tr')[1].find_all('td')
            player = counts[0].text

            for i in range(len(unit_names)):
                units[unit_names[i].text] = counts[i + 1].text.strip()
        else:
            if i["id"] == "tabShips":
                unit_names = i.find_all('tr')[0].find_all('div', class_='tooltip')
                counts = i.find_all('tr')[1].find_all('td')
                player = counts[0].text
                for i in range(len(unit_names)):
                    ships[unit_names[i].text] = counts[i + 1].text.strip()
    return units, ships


# Returns the rich table of the army and the fleet
def build_table(units, ships) -> ():
    army = Table(title="Army")
    army.add_column("Name")
    army.add_column("Count")
    for unit_key in units:
        army.add_row(unit_key, units[unit_key])

    fleet = Table(title="Fleet")
    fleet.add_column("Name")
    fleet.add_column("Count")
    for ship_key in ships:
        fleet.add_row(ship_key, ships[ship_key])

    return army, fleet


def request_troops(session, cityId) -> ():
    payload = {
        "view": "cityMilitary",
        "activeTab": "tabUnits",
        "cityId": cityId,
        "backgroundView": "city",
        "currentCityId": cityId,
        "actionRequest": actionRequest,
        "ajax": 1
    }
    resp = session.post(payloadPost=payload)
    resp = json.loads(resp, strict=False)
    troops_html = resp[1][1][1]
    units, ships = parse_units_from_html(troops_html)
    return units, ships


# Get all units from one city and make it look nice
def get_city_troops(session, event, stdin_fd, predetermined_input) -> None:
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input

    print("Choose the city to see millitary")
    chosen = chooseCity(session)

    # city = getCity(session.get(city_url + chosen['id']))
    units, ships = request_troops(session, chosen['id'])

    army, fleet = build_table(units, ships)

    console = Console()
    console.print(army)
    console.print(fleet)

    enter()
    event.set()


# Get units from all cities and make it look nice
def military_overview(session, event, stdin_fd, predetermined_input) -> None:
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    # Get all cities
    (ids, cities) = getIdsOfCities(session)

    # Stores the city id and the table of the army and fleet
    army_repo = []
    ship_repo = []
    for city_id in ids:
        army, ships = request_troops(session, city_id)
        tuple = build_table(army, ships)
        army_repo.append(tuple[0])
        ship_repo.append(tuple[1])

    table_grid = Table(title="Army overview", row_styles=["dim", ""])
    for i in ids:
        table_grid.add_column(cities[i]['name'], no_wrap=True)
    table_grid.add_row(*army_repo)
    table_grid.add_row(*ship_repo)

    console = Console()
    console.print(table_grid)
    enter()
    event.set()

import json
import os
import re
import sys

from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.varios import addThousandSeparator, wait, decodeUnicodeEscape


def getCityMilitaryData(session, city_id):
    params = {
        "view": "cityMilitary",
        "activeTab": "tabUnits",
        "cityId": city_id,
        "currentTab": "tabUnits",
        "currentCityId": city_id,
        "templateView": "cityMilitary",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    data = session.post(params=params)
    data = json.loads(data, strict=False)
    return data[1][1][1]


def extractTooltipsAndValues(data):
    tooltips = re.findall(r'<div[^>]*class="[^"]*tooltip[^"]*"[^>]*>(.*?)</div>', data)
    values = re.findall(r"<td>\s*([^<]+)\s*</td>", data)
    return tooltips, values


def parseUnits(html):
    tooltips, values = extractTooltipsAndValues(html)
    ground = {}
    ships = {}
    for i, (tooltip, value) in enumerate(zip(tooltips, values)):
        clean = re.sub(r'[\.,\s]|&nbsp;', '', value)
        if clean.isdigit():
            count = int(clean)
            if count > 0:
                name = decodeUnicodeEscape(tooltip.strip())
                if i <= 14:
                    ground[name] = count
                else:
                    ships[name] = count
    return ground, ships


resources_abbr = {"1": "(W)", "2": "(M)", "3": "(C)", "4": "(S)"}


def displayTable(city_names, ids, city_ground, city_ships, cities, show_ships):
    city_data = {}
    all_units = set()
    for city_id in ids:
        data = city_ships[city_id] if show_ships else city_ground[city_id]
        city_data[city_id] = data
        all_units.update(data.keys())

    all_units = sorted(all_units)

    if not all_units:
        kind = "troops" if not show_ships else "ships"
        print("No {} found in any city.".format(kind))
        return

    col_width = max(15, max(len(city_names[city_id]) for city_id in ids))

    header = "{:<25}".format("Unit" if not show_ships else "Ship")
    for city_id in ids:
        header += "|{:>{}}".format(city_names[city_id][:col_width], col_width)
    header += "|{:>{}}".format("Total", col_width)
    print(header)
    print("-" * len(header))

    grand_total = 0
    for unit_name in all_units:
        row = "{:<25}".format(unit_name[:25])
        unit_total = 0
        for city_id in ids:
            count = city_data[city_id].get(unit_name, 0)
            row += "|{:>{}}".format(addThousandSeparator(count), col_width)
            unit_total += count
        row += "|{:>{}}".format(addThousandSeparator(unit_total), col_width)
        print(row)
        grand_total += unit_total

    print("-" * len(header))
    total_row = "{:<25}".format("Total")
    for city_id in ids:
        city_total = sum(city_data[city_id].values())
        total_row += "|{:>{}}".format(addThousandSeparator(city_total), col_width)
    total_row += "|{:>{}}".format(addThousandSeparator(grand_total), col_width)
    print(total_row)


def displaySections(city_names, ids, city_ground, city_ships, cities, show_ships):
    try:
        term_height = os.get_terminal_size().lines
    except OSError:
        term_height = 20
    lines_printed = 3
    grand_total = 0
    any_data = False
    for city_id in ids:
        data = city_ships[city_id] if show_ships else city_ground[city_id]
        if not data:
            continue
        any_data = True
        abbr = resources_abbr.get(cities[city_id]["tradegood"], "")
        city_lines = ["{} {}:".format(city_names[city_id], abbr)]
        city_total = 0
        for unit_name in sorted(data):
            count = data[unit_name]
            city_lines.append("  {}: {}".format(unit_name, addThousandSeparator(count)))
            city_total += count
        city_lines.append("  Total: {}".format(addThousandSeparator(city_total)))

        if lines_printed + len(city_lines) + 2 >= term_height:
            enter()
            lines_printed = 0

        for line in city_lines:
            print(line)
        print()
        lines_printed += len(city_lines) + 1
        grand_total += city_total

    if not any_data:
        kind = "troops" if not show_ships else "ships"
        print("No {} found in any city.".format(kind))
        return
    print("-" * 30)
    print("Grand total: {}".format(addThousandSeparator(grand_total)))


def viewArmy(session, event, stdin_fd, predetermined_input):
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    try:
        banner()
        print("(0) Back")
        print("(1) View Troops")
        print("(2) View Fleet")

        selected = read(min=0, max=2, digit=True)
        if selected == 0:
            event.set()
            return

        banner()
        print("Gathering military data...\n")

        ids, cities = getIdsOfCities(session)

        city_names = {}
        city_ground = {}
        city_ships = {}

        for city_id in ids:
            city = cities[city_id]
            clean_name = decodeUnicodeEscape(city["name"])
            city_names[city_id] = clean_name
            print("  Reading {}...".format(clean_name))
            html = getCityMilitaryData(session, city["id"])
            ground, ships = parseUnits(html)
            city_ground[city_id] = ground
            city_ships[city_id] = ships
            wait(0.3, maxrandom=0.7)

        show_ships = selected == 2
        table_format = True
        while True:
            banner()
            title = "Fleet per city" if show_ships else "Troops per city"
            print("{}\n".format(title))
            if table_format:
                displayTable(city_names, ids, city_ground, city_ships, cities, show_ships)
            else:
                displaySections(city_names, ids, city_ground, city_ships, cities, show_ships)

            print()
            print("(0) Back")
            print("(1) View Troops")
            print("(2) View Fleet")
            fmt_name = "Sections" if table_format else "Table"
            print("(3) Format: {}".format(fmt_name))
            print()
            selected = read(min=0, max=3, digit=True)
            if selected == 0:
                event.set()
                return
            if selected == 3:
                table_format = not table_format
            else:
                show_ships = selected == 2

    except KeyboardInterrupt:
        event.set()
        return

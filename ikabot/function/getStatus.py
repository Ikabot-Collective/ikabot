#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import gettext
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.naval import *
from ikabot.helpers.varios import *
from ikabot.helpers.resources import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.market import getGold
from rich import print as rich_print
from rich.table import Table

t = gettext.translation('getStatus', localedir, languages=languages, fallback=True)
_ = t.gettext

getcontext().prec = 30


def getStatus(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    try:
        banner()

        (ids, __) = getIdsOfCities(session)
        total_resources = [0] * len(materials_names)
        total_production = [0] * len(materials_names)
        total_wine_consumption = 0
        available_ships = 0
        total_ships = 0
        for id in ids:
            session.get('view=city&cityId={}'.format(id), noIndex=True)
            data = session.get("view=updateGlobalData&ajax=1", noIndex=True)
            json_data = json.loads(data, strict=False)
            json_data = json_data[0][1]['headerData']
            if json_data['relatedCity']['owncity'] != 1:
                continue
            wood = Decimal(json_data['resourceProduction'])
            good = Decimal(json_data['tradegoodProduction'])
            typeGood = int(json_data['producedTradegood'])
            total_production[0] += wood * 3600
            total_production[typeGood] += good * 3600
            total_wine_consumption += json_data['wineSpendings']
            total_resources[0] += json_data['currentResources']['resource']
            total_resources[1] += json_data['currentResources']['1']
            total_resources[2] += json_data['currentResources']['2']
            total_resources[3] += json_data['currentResources']['3']
            total_resources[4] += json_data['currentResources']['4']
            available_ships = json_data['freeTransporters']
            total_ships = json_data['maxTransporters']
            total_gold = int(Decimal(json_data['gold']))
            total_gold_production = int(
                Decimal(json_data['scientistsUpkeep'] + json_data['income'] + json_data['upkeep']))
        rich_print(_('Ships {:d}/{:d}').format(int(available_ships), int(total_ships)))

        # Available table
        available_table = Table(title="Available", highlight=True, min_width=100)

        for i in range(len(materials_names)):
            available_table.add_column(f"{materials_names_english[i]}", justify="center", min_width=10, vertical="middle")

        available_table.add_row(f"{'{:>10,}'.format(total_resources[0]).replace(',', '.')}",
                                f"{'{:>10,}'.format(total_resources[1]).replace(',', '.')}",
                                f"{'{:>10,}'.format(total_resources[2]).replace(',', '.')}",
                                f"{'{:>10,}'.format(total_resources[3]).replace(',', '.')}",
                                f"{'{:>10,}'.format(total_resources[4]).replace(',', '.')}")

        rich_print(available_table)

        def get_production_str(number) -> str:
            raw = f"{'{:>10,}'.format(number).replace(',', '.')}"
            spl = raw.split('.')
            final_string = None
            if len(spl) >= 1:
                spl[len(spl) - 1] = spl[len(spl) - 1][:2]  # keep only 2 digits from the floating number
                final_string = ".".join(spl)
            return final_string if final_string is not None else raw

        production_table = Table(title="Production", highlight=True, min_width=100)
        for i in range(len(materials_names)):
            production_table.add_column(f"{materials_names_english[i]}", justify="center", min_width=10, vertical="middle")
        production_table.add_row(get_production_str(total_production[0]), get_production_str(total_production[1]),
                                 get_production_str(total_production[2]), get_production_str(total_production[3]),
                                 get_production_str(total_production[4]))

        rich_print(production_table)

        print("Gold : {}, Gold production : {}".format(addThousandSeparator(total_gold, ' '),
                                                       addThousandSeparator(total_gold_production, ' ')))
        print("Wine consumption : {}".format(addThousandSeparator(total_wine_consumption, ' ')), end='')

        print(_('\nOf which city do you want to see the state?'))
        city = chooseCity(session)
        banner()

        (wood, good, typeGood) = getProductionPerSecond(session, city['id'])

        resources_abbreviations = {1: _('(W)'), 2: _('(M)'), 3: _('(C)'), 4: _('(S)')}
        rich_colors = {1: 'purple', 2: 'gray', 3: 'blue', 4: 'yellow'}
        resource_abb = resources_abbreviations[typeGood]

        rich_print(f"[{rich_colors[typeGood]}]{city['cityName']} {resource_abb}[/{rich_colors[typeGood]}]")

        resources = city['recursos']
        storageCapacity = city['storageCapacity']
        color_resources = []
        for i in range(len(materials_names)):
            if resources[i] == storageCapacity:
                color_resources.append(bcolors.RED)
            else:
                color_resources.append(bcolors.ENDC)
        rich_print(_('Storage:'))
        rich_print(addThousandSeparator(storageCapacity))

        resources_table = Table(title="Resources", highlight=True)
        for i in materials_names:
            resources_table.add_column(i, justify="center", min_width=10, vertical="middle")
        resources_table.add_row(f"{addThousandSeparator(resources[0])}", f"{addThousandSeparator(resources[1])}",
                                f"{addThousandSeparator(resources[2])}", f"{addThousandSeparator(resources[3])}",
                                f"{addThousandSeparator(resources[4])}")
        rich_print(resources_table)

        rich_print(_('Production:'))
        rich_print(
            '{}:{} {}:{}'.format(materials_names[0], addThousandSeparator(wood * 3600), materials_names[typeGood],
                                 addThousandSeparator(good * 3600)))

        hasTavern = 'tavern' in [building['building'] for building in city['position']]
        if hasTavern:
            consumption_per_hour = city['consumo']
            if consumption_per_hour == 0:
                rich_print('[red bold]Does not consume wine![/red bold]')
            else:
                if typeGood == 1 and (good * 3600) > consumption_per_hour:
                    elapsed_time_run_out = '∞'
                else:
                    consumption_per_second = Decimal(consumption_per_hour) / Decimal(3600)
                    remaining_resources_to_consume = Decimal(resources[1]) / Decimal(consumption_per_second)
                    elapsed_time_run_out = daysHoursMinutes(remaining_resources_to_consume)
                rich_print(f"There is wine for: {elapsed_time_run_out}")

        for building in [building for building in city['position'] if building['name'] != 'empty']:
            if building['isMaxLevel'] is True:
                color = bcolors.BLACK
            elif building['canUpgrade'] is True:
                color = 'green'
            else:
                color = 'red'

            level = building['level']
            if level < 10:
                level = ' ' + str(level)
            else:
                level = str(level)
            if building['isBusy'] is True:
                level = level + '+'

            rich_print(f"lv:{level}\t[{color}]{building['name']}[/{color}]")

        enter()
        print('')
        event.set()
    except KeyboardInterrupt:
        event.set()
        return

#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import gettext
from dataclasses import dataclass
from decimal import *
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.naval import *
from ikabot.helpers.varios import *
from ikabot.helpers.resources import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.market import printGoldForAllCities

t = gettext.translation('getStatus', localedir, languages=languages, fallback=True)
_ = t.gettext

getcontext().prec = 30

def printProgressBar(msg, current, total):
    banner()
    loaded = "#" * (current - 1)
    waiting = "." * (total - current)
    print("{}: [{}={}] {}/{}".format(msg, loaded, waiting, current, total))



def getStatusImproved(session, event, stdin_fd, predetermined_input):
    '''
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    '''
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input

    # region Config
    COLUMN_SEPARATOR = ' | '
    STORAGE_COLUMN_MAX_LENGTH = 10
    RESOURCE_COLUMN_MAX_LENGTH = 10
    RESOURCE_COLORS = [bcolors.WOOD, bcolors.HEADER, bcolors.STONE, bcolors.BLUE, bcolors.WARNING]
    TABLE_WIDTH = MAXIMUM_CITY_NAME_LENGTH + RESOURCE_COLUMN_MAX_LENGTH + len(materials_names) * RESOURCE_COLUMN_MAX_LENGTH + (len(materials_names) + 2 - 1) * len(COLUMN_SEPARATOR)
    TABLE_ROW_SEPARATOR = '-' * TABLE_WIDTH
    TOTAL = 'TOTAL'

    def get_increment(incr):
        if incr == 0:
            return " " * RESOURCE_COLUMN_MAX_LENGTH
        color = bcolors.GREEN if incr > 0 else bcolors.RED
        res_incr = "{: >{len}}".format(str(format(incr, '+,')), len=RESOURCE_COLUMN_MAX_LENGTH)
        return color + res_incr + bcolors.ENDC

    def get_storage(capacity, available):
        res = "{: >{len}}".format(str(format(available, ',')), len=RESOURCE_COLUMN_MAX_LENGTH)
        if capacity * 0.2 > capacity - available:
            res = bcolors.WARNING + res + bcolors.ENDC
        return res
    # endregion

    try:
        banner()

        [city_ids, _] = getIdsOfCities(session, False)
        cities = []

        # available_ships = 0
        # total_ships = 0

        # region Retrieve cities data
        for res_ind, city_id in enumerate(city_ids):
            printProgressBar("Retrieving cities data", res_ind+1, len(city_ids))
            html = session.get(city_url + city_id)
            print(html.replace("\n", "").replace("  ", "").replace("  ", "").replace("  ", ""))
            return
            city = getCity(html)

            resource_production = getProductionPerSecond(session, city_id)
            resource_production_per_hour = [int(resource_production[0] * SECONDS_IN_HOUR), 0, 0, 0, 0]
            resource_production_per_hour[int(resource_production[2])] = int(resource_production[1] * SECONDS_IN_HOUR)
            city['resourceProductionPerHour'] = resource_production_per_hour
            cities.append(city)
        # endregion

        banner()
        printGoldForAllCities(session, city_ids[0])

        # region Print resources table
        # city |  storage | wood | wine | stone | crystal | sulfur
        print("\n\nResources:\n")
        materials = [(RESOURCE_COLORS[ind] + "{: ^{len}}".format(r, len=RESOURCE_COLUMN_MAX_LENGTH) + bcolors.ENDC) for ind, r in enumerate(materials_names)]

        city_name_header_column = " " * MAXIMUM_CITY_NAME_LENGTH
        storage_header_column = "{: ^{len}}".format("Storage", len=STORAGE_COLUMN_MAX_LENGTH)
        print(COLUMN_SEPARATOR.join([city_name_header_column, storage_header_column] + materials))

        total = {
            'cityName': TOTAL,
            'storageCapacity': sum(c['storageCapacity'] for c in cities),
            'availableResources': [sum(x) for x in zip(*[c['availableResources'] for c in cities])],
            'resourceProductionPerHour': [sum(x) for x in zip(*[c['resourceProductionPerHour'] for c in cities])],
            'wineConsumptionPerHour': sum(c['wineConsumptionPerHour'] for c in cities)
        }

        for city in cities + [total]:
            city_name = city['cityName']
            if city_name == TOTAL:
                print(TABLE_ROW_SEPARATOR.replace("-", "="))
            else:
                print(TABLE_ROW_SEPARATOR)

            storage_capacity = city['storageCapacity']
            available_resources = city['availableResources']
            row1 = [
                "{: >{len}}".format(city_name, len=MAXIMUM_CITY_NAME_LENGTH),
                "{: >{len}}".format(str(format(storage_capacity, ',')), len=STORAGE_COLUMN_MAX_LENGTH),
            ]
            row2 = [
                " " * MAXIMUM_CITY_NAME_LENGTH,
                " " * STORAGE_COLUMN_MAX_LENGTH,
            ]
            for res_ind, resource in enumerate(materials_names):
                res_in_storage = available_resources[res_ind]
                row1.append(get_storage(storage_capacity, res_in_storage))

                res_incr = city['resourceProductionPerHour'][res_ind]
                if res_ind == 1:
                    res_incr -= city['wineConsumptionPerHour']
                row2.append(get_increment(res_incr))

            print(COLUMN_SEPARATOR.join(row1))
            print(COLUMN_SEPARATOR.join(row2))
        # endregion

            # print(getCity(session.get('view=city&cityId={}'.format(cityId), noIndex=True)))

            # data = session.get('view=updateGlobalData&ajax=1', noIndex=True)
            # json_data = json.loads(data, strict=False)
            # print("\n\n\ndata\n")
            # print(data)
            # print("\n\n\n\n")
        #
        #     print(city)
        #
        #     json_data = json_data[0][1]['headerData']
        #     if json_data['relatedCity']['owncity'] != 1:
        #         continue
        #     # print(json_data)
        #     wood = Decimal(json_data['resourceProduction'])
        #     good = Decimal(json_data['tradegoodProduction'])
        #     typeGood = int(json_data['producedTradegood'])
        #     total_production[0] += wood * 3600
        #     total_production[typeGood] += good * 3600
        #     total_wine_consumption += json_data['wineSpendings']
        #     housing_space = int(json_data['currentResources']['population'])
        #     citizens = int(json_data['currentResources']['citizens'])
        #     total_housing_space += housing_space
        #     total_citizens += citizens
        #     total_resources[0] += json_data['currentResources']['resource']
        #     total_resources[1] += json_data['currentResources']['1']
        #     total_resources[2] += json_data['currentResources']['2']
        #     total_resources[3] += json_data['currentResources']['3']
        #     total_resources[4] += json_data['currentResources']['4']
        #     available_ships = json_data['freeTransporters']
        #     total_ships = json_data['maxTransporters']
        #     total_gold = int(Decimal(json_data['gold']))
        #     total_gold_production = int(Decimal(json_data['scientistsUpkeep'] + json_data['income'] + json_data['upkeep']))
        #
        # print("\n\n\n\n\n\n\n\n")
        # print(_('Ships {:d}/{:d}').format(int(available_ships), int(total_ships)))
        # print(_('\nTotal:'))
        # print('{:>10}'.format(' '), end='|')
        # for i in range(len(materials_names)):
        #     print('{:>12}'.format(materials_names_english[i]), end='|')
        # print()
        # print('{:>10}'.format('Available'), end='|')
        # for i in range(len(materials_names)):
        #     print('{:>12}'.format(addThousandSeparator(total_resources[i])), end='|')
        # print()
        # print('{:>10}'.format('Production'), end='|')
        # for i in range(len(materials_names)):
        #     print('{:>12}'.format(addThousandSeparator(total_production[i])), end='|')
        # print()
        # print('Housing Space: {}, Citizens: {}'.format(addThousandSeparator(total_housing_space), addThousandSeparator(citizens)))
        # print('Gold: {}, Gold production: {}'.format(addThousandSeparator(total_gold), addThousandSeparator(total_gold_production)))
        # print('Wine consumption: {}'.format(addThousandSeparator(total_wine_consumption)), end='')
        #
        #




























        #
        #
        #
        #
        # print(_('\nOf which city do you want to see the state?'))
        # city = chooseCity(session)
        # banner()
        #
        # (wood, good, typeGood) = getProductionPerSecond(session, city['id'])
        # print('\033[1m{}{}{}'.format(color_arr[int(typeGood)], city['cityName'], color_arr[0]))
        #
        # resources = city['availableResources']
        # storageCapacity = city['storageCapacity']
        # color_resources = []
        # for i in range(len(materials_names)):
        #     if resources[i] == storageCapacity:
        #         color_resources.append(bcolors.RED)
        #     else:
        #         color_resources.append(bcolors.ENDC)
        # print(_('Population:'))
        # print('{}: {} {}: {}'.format('Housing space', addThousandSeparator(housing_space), 'Citizens', addThousandSeparator(citizens)))
        # print(_('Storage: {}'.format(addThousandSeparator(storageCapacity))))
        # print(_('Resources:'))
        # for i in range(len(materials_names)):
        #     print('{} {}{}{} '.format(materials_names[i], color_resources[i], addThousandSeparator(resources[i]), bcolors.ENDC), end='')
        # print('')
        #
        # print(_('Production:'))
        # print('{}: {} {}: {}'.format(materials_names[0], addThousandSeparator(wood*3600), materials_names[typeGood], addThousandSeparator(good*3600)))
        #
        # hasTavern = 'tavern' in [building['building'] for building in city['position']]
        # if hasTavern:
        #     consumption_per_hour = city['wineConsumption']
        #     if consumption_per_hour == 0:
        #         print(_('{}{}Does not consume wine!{}').format(bcolors.RED, bcolors.BOLD, bcolors.ENDC))
        #     else:
        #         if typeGood == 1 and (good*3600) > consumption_per_hour:
        #             elapsed_time_run_out = '∞'
        #         else:
        #             consumption_per_second = Decimal(consumption_per_hour) / Decimal(3600)
        #             remaining_resources_to_consume = Decimal(resources[1]) / Decimal(consumption_per_second)
        #             elapsed_time_run_out = daysHoursMinutes(remaining_resources_to_consume)
        #         print(_('There is wine for: {}').format(elapsed_time_run_out))
        #
        # for building in [building for building in city['position'] if building['name'] != 'empty']:
        #     if building['isMaxLevel'] is True:
        #         color = bcolors.BLACK
        #     elif building['canUpgrade'] is True:
        #         color = bcolors.GREEN
        #     else:
        #         color = bcolors.RED
        #
        #     level = building['level']
        #     if level < 10:
        #         level = ' ' + str(level)
        #     else:
        #         level = str(level)
        #     if building['isBusy'] is True:
        #         level = level + '+'
        #
        #     print(_('lv:{}\t{}{}{}').format(level, color, building['name'], bcolors.ENDC))

        enter()
        print('')
        event.set()
    except KeyboardInterrupt:
        event.set()
        return

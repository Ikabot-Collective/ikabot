#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import gettext
import json
from ikabot.config import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.getJson import *
from ikabot.helpers.resources import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *

t = gettext.translation('donate', localedir, languages=languages, fallback=True)
_ = t.gettext

def get_number(s):
    return int(s.replace(',', '').replace('.', ''))

def rightAligh(data, len):
    return "{:>{len}}".format(data, len=len)

def printProgressBar(msg, current, total):
    banner()
    loaded = "#" * (current - 1)
    waiting = "." * (total - current)
    print("{}: [{}={}] {}/{}".format(msg, loaded, waiting, current, total))


def islandWorkplaces(session, event, stdin_fd, predetermined_input):
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

    # region Config
    column_separator = ' | '
    columns = [
        'Id',
        'City',
        'Resource',
        'Production',
        'Workers',
        'Overcharged',
        'level',
        'Upgrade wood required',
    ]
    column_length = [3, MAXIMUM_CITY_NAME_LENGTH, 13, 13, 13, 13, 5, 23]
    resource_colors = [
        '\033[0;33m',
        bcolors.HEADER,
        bcolors.STONE,
        bcolors.BLUE,
        bcolors.WARNING
    ]
    def get_view(material_ind):
        return 'resource' if material_ind == 0 else 'tradegood'

    def extract_workplace_data(init_data, material_ind, json):
        '''
        Extracts data from json
        :param init_data: dict with basic city data
        :param material_ind: int
        :param json:
        :return:
        '''
        view = get_view(material_ind)
        data = dict(init_data)
        background_data = json[0][1]['backgroundData']
        template_data = json[2][1]
        slider_data = template_data['js_ResourceSlider']['slider']
        end_upgrade_time = int(background_data[view + 'EndUpgradeTime'])  # resourceEndUpgradeTime / tradegoodEndUpgradeTime
        data.update({
            'level': background_data[view + 'Level'],  # resourceLevel / tradegoodLevel
            'upgradeEndTime': end_upgrade_time,
            'upgrading': end_upgrade_time > 0,
            'requiredWoodForNextLevel': 0,
            'material': material_ind,
            'totalWorkers': template_data['valueWorkers'],
            'freeCitizens': template_data['valueCitizens'],
            'production': template_data['js_resource_tooltip_total_production']['text'],
            'maxWorkers': slider_data['max_value'],
            'overchargedWorkers': slider_data['overcharge'],
        })

        if not data['upgrading'] and json[1][0] == 'changeView':
            # changeView -> resources
            needed, donated = re.findall(r'<li class="wood">(.*?)</li>', json[1][1][1])
            data['requiredWoodForNextLevel'] = get_number(needed) - get_number(donated)

        return data

    def get_workplace_data(init_data, material_ind, island_id):
        '''
        Retrieves data for workplace / resource information
        :param init_data: dict with city data
        :param material_ind: for which material to get data
        :param island_id: for which island to get data
        :return: resource dict
        '''
        res_type = 'resource' if material_ind == 0 else material_ind
        view = get_view(material_ind)
        url = 'view={view}&type={type}&islandId={islandId}&backgroundView=island&currentIslandId={islandId}&actionRequest={actionRequest}&ajax=1'.format(view=view, type=res_type, islandId=island_id, actionRequest=actionRequest)
        resp = json.loads(session.post(url), strict=False)
        return extract_workplace_data(init_data, material_ind, resp)

    def get_workplaces():
        [city_ids, cities] = getIdsOfCities(session, False)
        loading_msg = "Loading workplaces for cities"
        all_workplaces = 3 * len(city_ids)
        workplaces = []

        for city_ind, city_id in enumerate(city_ids):
            printProgressBar(loading_msg, city_ind*3+1, all_workplaces)
            city = getCity(session.get(city_url + city_id))

            island_id = city['islandId']
            city_data = {
                'cityId': city['id'],
                'cityName': city['cityName'],
                'islandId': island_id,
            }

            printProgressBar(loading_msg, city_ind*3+2, all_workplaces)
            workplaces.append(get_workplace_data(city_data, 0, island_id))

            printProgressBar(loading_msg, city_ind*3+3, all_workplaces)
            workplaces.append(get_workplace_data(city_data, cities[city_id]['tradegood'], island_id))

        banner()
        return workplaces

    def print_workplaces(workplaces):
        # Print header
        print(column_separator.join([rightAligh(c, cl) for c, cl in zip(columns, column_length)]))

        # Print table
        for ind, workplace in enumerate(workplaces):
            if ind % 2 == 0:
                # print separator between cities
                print('-' * (sum(column_length) + (len(column_length) - 1) * len(column_separator)))

            total_workers = workplace['totalWorkers']
            max_workers = workplace['maxWorkers']
            material = workplace['material']
            upgrading = workplace['upgrading']
            overcharged = workplace['overchargedWorkers']

            # Construct colors for data
            colors = [
                '',
                '',
                resource_colors[material],
                '',
                bcolors.GREEN if total_workers >= max_workers else bcolors.RED,
                bcolors.WARNING if total_workers > max_workers else '',
                bcolors.GREEN if upgrading else '',
                bcolors.WARNING if upgrading else '',
            ]

            # Construct data
            row = [
                str(ind+1) + ")",
                workplace['cityName'] if ind % 2 == 0 else '',
                materials_names[material],
                '+{}/h'.format(addThousandSeparator(workplace['production'])),
                "{} / {}".format(
                    addThousandSeparator(min(total_workers, max_workers)),
                    addThousandSeparator(max_workers)
                ),
                "{} / {}".format(
                    0 if overcharged == 0 else min(0, total_workers - max_workers),
                    overcharged
                ),
                workplace['level'] + ('+' if upgrading else ' '),
                addThousandSeparator(workplace['requiredWoodForNextLevel']) if not upgrading else "Upgrading for " + daysHoursMinutes(workplace['upgradeEndTime'])
            ]

            # Combine and print
            print(column_separator.join([
                (color + rightAligh(data, length) + bcolors.ENDC)
                for color, data, length in zip(colors, row, column_length)
            ]))

    # endregion

    try:
        workplaces = get_workplaces()

        while True:
            print_workplaces(workplaces)
            return

        city = chooseCity(session)

        banner()
        island_id = city['islandId']
        island = getIsland(session.get(island_url + island_id))

        island_type = island['tipo']
        resource_name = tradegoods_names[0]
        tradegood_name = tradegoods_names[int(island_type)]

        # get resource information
        url = 'view=resource&type=resource&islandId={0}&backgroundView=island&currentIslandId={0}&actionRequest={1}&ajax=1'.format(island_id, actionRequest)
        resp = session.post(url)
        resp = json.loads(resp, strict=False)

        resourceLevel = resp[0][1]['backgroundData']['resourceLevel']
        tradegoodLevel = resp[0][1]['backgroundData']['tradegoodLevel']
        resourceEndUpgradeTime = int(resp[0][1]['backgroundData']['resourceEndUpgradeTime'])
        resourceUpgrading = resourceEndUpgradeTime > 0
        tradegoodEndUpgradeTime = int(resp[0][1]['backgroundData']['tradegoodEndUpgradeTime'])
        tradegoodUpgrading = tradegoodEndUpgradeTime > 0

        if resourceUpgrading:
            resourceUpgradeMsg = _('(upgrading, ends in:{})').format(daysHoursMinutes(resourceEndUpgradeTime))
        else:
            resourceUpgradeMsg = ''
        if tradegoodUpgrading:
            tradegoodUpgradeMsg = _('(upgrading, ends in:{})').format(daysHoursMinutes(tradegoodEndUpgradeTime))
        else:
            tradegoodUpgradeMsg = ''

        html = resp[1][1][1]
        wood_total_needed, wood_donated = re.findall(r'<li class="wood">(.*?)</li>', html)
        wood_total_needed = wood_total_needed.replace(',', '').replace('.', '')
        wood_total_needed = int(wood_total_needed)
        wood_donated = wood_donated.replace(',', '').replace('.', '')
        wood_donated = int(wood_donated)

        if resourceUpgrading and tradegoodUpgrading:
            print(_('Both the {} (ends in:{}) and the {} (ends in:{}) are being upgraded rigth now.\n'.format(resource_name, daysHoursMinutes(resourceEndUpgradeTime), tradegood_name, daysHoursMinutes(tradegoodEndUpgradeTime))))
            enter()
            event.set()
            return

        print('{} lv:{} {}'.format(resource_name, resourceLevel, resourceUpgradeMsg))
        print('{} / {} ({}%)\n'.format(addThousandSeparator(wood_donated), addThousandSeparator(wood_total_needed), addThousandSeparator(int((100 * wood_donated) / wood_total_needed))))

        # get tradegood information
        url = 'view=tradegood&type={0}&islandId={1}&backgroundView=island&currentIslandId={1}&actionRequest={2}&ajax=1'.format(island_type, island_id, actionRequest)
        resp = session.post(url)

        resp = json.loads(resp, strict=False)
        html = resp[1][1][1]
        tradegood_total_needed, tradegood_donated = re.findall(r'<li class="wood">(.*?)</li>', html)
        tradegood_total_needed = tradegood_total_needed.replace(',', '').replace('.', '')
        tradegood_total_needed = int(tradegood_total_needed)
        tradegood_donated = tradegood_donated.replace(',', '').replace('.', '')
        tradegood_donated = int(tradegood_donated)

        print('{} lv:{} {}'.format(tradegood_name, tradegoodLevel, tradegoodUpgradeMsg))
        print('{} / {} ({}%)\n'.format(addThousandSeparator(tradegood_donated), addThousandSeparator(tradegood_total_needed), addThousandSeparator(int((100 * tradegood_donated) / tradegood_total_needed))))

        print(_('Wood available:{}\n').format(addThousandSeparator(woodAvailable)))

        if resourceUpgrading is False and tradegoodUpgrading is False:
            msg = _('Donate to {} (1) or {} (2)?:').format(resource_name, tradegood_name)
            donation_type = read(msg=msg, min=1, max=2)
            name = resource_name if donation_type == 1 else tradegood_name
            print('')
        else:
            if resourceUpgrading is False and tradegoodUpgrading is True:
                donation_type = 1
                name = resource_name
            else:
                donation_type = 2
                name = tradegood_name
            print('Donate to:{}\n'.format(name))

        donation_type = 'resource' if donation_type == 1 else 'tradegood'

        amount = read(min=0, max=woodAvailable, default=0, additionalValues=['all','half'], msg=_('Amount (number, all, half):'))
        if amount == 'all':
            amount = woodAvailable
        elif amount == 'half':
            amount = woodAvailable // 2
        elif amount == 0:
            event.set()
            return
        print(_('Will donate {} to the {}?').format(addThousandSeparator(amount), name))
        print(_('\nProceed? [Y/n]'))
        rta = read(values=['y', 'Y', 'n', 'N', ''])
        if rta.lower() == 'n':
            event.set()
            return

        # do the donation
        session.post(params={'islandId': island_id, 'type': donation_type, 'action': 'IslandScreen', 'function': 'donate', 'donation': amount, 'backgroundView': 'island', 'templateView': 'resource', 'actionRequest': actionRequest, 'ajax': '1'})

        print('\nDonation successful.')
        enter()
        event.set()
        return
    except KeyboardInterrupt:
        event.set()
        return

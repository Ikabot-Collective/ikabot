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
    def get_workplace_data(init_data, material_ind, island_id):
        '''
        Retrieves data for workplace / resource information
        :param init_data: dict with city data
        :param material_ind: for which material to get data
        :param island_id: for which island to get data
        :return: resource dict
        '''
        type = 'resource' if material_ind == 0 else material_ind
        view = 'resource' if material_ind == 0 else 'tradegood'
        url = 'view={view}&type={type}&islandId={islandId}&backgroundView=island&currentIslandId={islandId}&actionRequest={actionRequest}&ajax=1'.format(view=view, type=type, islandId=island_id, actionRequest=actionRequest)
        resp = json.loads(session.post(url), strict=False)
        data = dict(init_data)
        end_upgrade_time = int(resp[0][1]['backgroundData'][view + 'EndUpgradeTime'])  # resourceEndUpgradeTime / tradegoodEndUpgradeTime
        data.update({
            'level': resp[0][1]['backgroundData'][view + 'Level'],  # resourceLevel / tradegoodLevel
            'upgradeEndTime': end_upgrade_time,
            'upgrading': end_upgrade_time > 0,
            'requiredWoodForNextLevel': 0,
        })

        if not data['upgrading']:
            html = resp[1][1][1]
            wood_total_needed, wood_donated = re.findall(r'<li class="wood">(.*?)</li>', html)
            wood_total_needed = wood_total_needed.replace(',', '').replace('.', '')
            wood_total_needed = int(wood_total_needed)
            wood_donated = wood_donated.replace(',', '').replace('.', '')
            wood_donated = int(wood_donated)
            data['requiredWoodForNextLevel'] = wood_total_needed - wood_donated

        print(data)
        return data


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

        return workplaces
    # endregion

    try:
        workplaces = get_workplaces()
        print(workplaces)
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

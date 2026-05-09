#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import re
import traceback
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *

SATISFACTION_BUFFER = 5


class TavernManager:
    def __init__(self, session, notification_mode=3):
        self.session = session
        self.notification_mode = notification_mode
        self._cache = {}

    def _get_tavern_data(self, city, tavern, force_refresh=False):
        city_id = city['id']
        if not force_refresh and city_id in self._cache:
            return self._cache[city_id]

        building_position = tavern['position']
        tavern_params = {
            'view': 'tavern',
            'cityId': city_id,
            'position': building_position,
            'backgroundView': 'city',
            'currentCityId': city_id,
            'ajax': '1',
        }
        tavern_response = self.session.post(params=tavern_params)

        try:
            response_data = json.loads(tavern_response)
        except (json.JSONDecodeError, ValueError):
            return None

        current_level = 0
        action_code = None
        consumption_values = []
        sat_per_wine = []

        for item in response_data:
            if not isinstance(item, list) or len(item) < 2:
                continue

            if item[0] == "changeView" and isinstance(item[1], list) and len(item[1]) >= 2:
                tavern_html = item[1][1]
                dropdown_pattern = re.findall(
                    r'<option[^>]*value="(\d+)"[^>]*>(\d+)', tavern_html
                )
                for level_str, wine_str in dropdown_pattern:
                    consumption_values.append((int(level_str), int(wine_str)))

            elif item[0] == "updateTemplateData" and isinstance(item[1], dict):
                load_js = item[1].get("load_js", {})
                if isinstance(load_js, dict) and "params" in load_js:
                    try:
                        js_data = json.loads(load_js["params"])
                        if "wineServeLevel" in js_data:
                            current_level = int(js_data["wineServeLevel"])
                        if "satPerWine" in js_data:
                            sat_per_wine = js_data["satPerWine"]
                    except (json.JSONDecodeError, ValueError, KeyError):
                        pass

            elif item[0] == "updateGlobalData" and isinstance(item[1], dict):
                if "actionRequest" in item[1]:
                    action_code = item[1]["actionRequest"]

        result = {
            'current_level': current_level,
            'action_code': action_code,
            'consumption_values': consumption_values,
            'sat_per_wine': sat_per_wine,
        }
        self._cache[city_id] = result
        return result

    def _wine_at_level(self, consumption_values, level):
        return next((w for l, w in consumption_values if l == level), 0)

    def _apply_level(self, city, tavern, target_level, tavern_data):
        params = {
            'action': 'CityScreen',
            'function': 'assignWinePerTick',
            'cityId': city['id'],
            'position': tavern['position'],
            'amount': target_level,
            'backgroundView': 'city',
            'currentCityId': city['id'],
            'templateView': 'tavern',
            'actionRequest': tavern_data['action_code'],
            'ajax': '1',
        }
        self.session.post(params=params)
        self._cache.pop(city['id'], None)

    def _get_town_hall_data(self, city_id, city_data):
        town_hall_position = next(
            (b['position'] for b in city_data['position'] if b['building'] == 'townHall'),
            None
        )
        if town_hall_position is None:
            return None

        th_params = {
            'view': 'townHall',
            'cityId': city_id,
            'position': town_hall_position,
            'backgroundView': 'city',
            'currentCityId': city_id,
            'ajax': '1',
        }
        th_response = self.session.post(params=th_params)

        try:
            th_data = json.loads(th_response)
        except (json.JSONDecodeError, ValueError):
            return None

        th_html = next(
            (item[1][1] for item in th_data
             if isinstance(item, list) and item[0] == "changeView"
             and isinstance(item[1], list) and len(item[1]) >= 2),
            None
        )
        if not th_html:
            return None

        growth_match = re.search(r'id="js_TownHallPopulationGrowthValue">([0-9,.\xa0\s-]+)', th_html)
        satisfaction_match = re.search(
            r'id="js_TownHallHappinessLargeValue"[^>]*>([0-9,.\xa0\s-]+)', th_html
        )
        occupied_match = re.search(
            r'id="js_TownHallOccupiedSpace"[^>]*>([0-9,.\xa0\s]+)', th_html
        )
        max_inhabitants_match = re.search(
            r'id="js_TownHallMaxInhabitants"[^>]*>([0-9,.\xa0\s]+)', th_html
        )

        if not growth_match or not satisfaction_match:
            return None

        resource_shortage = bool(
            re.search(r'class="[^"]*shortage[^"]*"', th_html, re.IGNORECASE)
        )

        return {
            'growth_rate': self._parse_decimal(growth_match.group(1)),
            'total_satisfaction': self._parse_signed_int(satisfaction_match.group(1)),
            'resource_shortage': resource_shortage,
            'current_pop': self._parse_int(occupied_match.group(1)) if occupied_match else None,
            'max_pop': self._parse_int(max_inhabitants_match.group(1)) if max_inhabitants_match else None,
        }

    @staticmethod
    def _parse_int(s):
        digits = re.sub(r'\D', '', s)
        return int(digits) if digits else 0

    @staticmethod
    def _parse_signed_int(s):
        # Integer that may carry a sign and thousands separators; e.g. "-1,234"
        negative = '-' in s
        digits = re.sub(r'\D', '', s)
        if not digits:
            return 0
        n = int(digits)
        return -n if negative else n

    @staticmethod
    def _parse_decimal(s):
        s = s.strip().replace('\xa0', '').replace(' ', '')
        if not s or s in ('-', '.'):
            return 0.0
        # Decide which separator is the decimal mark: whichever comes last.
        last_dot = s.rfind('.')
        last_comma = s.rfind(',')
        if last_comma > last_dot:
            # comma is decimal mark
            s = s.replace('.', '').replace(',', '.')
        else:
            # dot is decimal mark (or no decimal mark)
            s = s.replace(',', '')
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _optimize_for_satisfaction(self, city, tavern, tavern_data, current_satisfaction):
        sat_per_wine = tavern_data['sat_per_wine']
        current_level = tavern_data['current_level']
        consumption_values = tavern_data['consumption_values']

        if not sat_per_wine:
            return None

        if current_level < len(sat_per_wine):
            base_satisfaction = current_satisfaction - sat_per_wine[current_level]
        else:
            base_satisfaction = current_satisfaction

        optimal_level = current_level
        for level in range(len(sat_per_wine)):
            projected = base_satisfaction + sat_per_wine[level]
            if projected >= SATISFACTION_BUFFER:
                optimal_level = level
                break

        if optimal_level == current_level:
            return None

        current_wine = self._wine_at_level(consumption_values, current_level)
        new_wine = self._wine_at_level(consumption_values, optimal_level)
        self._apply_level(city, tavern, optimal_level, tavern_data)
        return f"L{current_level}({current_wine}/h)→L{optimal_level}({new_wine}/h)"

    def process_equilibrium(self, cities_ids, cities):
        self._cache.clear()
        results = []

        for city_id in cities_ids:
            city = cities[city_id]
            result = {
                'name': city['name'],
                'status': None,
                'pop': '',
                'satisfaction': '',
                'note': '',
            }

            try:
                html = self.session.get(city_url + str(city_id))
                city_data = getCity(html)

                tavern = next(
                    (b for b in city_data['position'] if b['building'] == 'tavern'),
                    None
                )

                if not tavern:
                    result.update({'status': 'SKIP', 'note': 'No tavern'})
                    results.append(result)
                    continue

                th_data = self._get_town_hall_data(city_id, city_data)
                if not th_data:
                    result.update({'status': 'SKIP', 'note': 'Could not load town hall'})
                    results.append(result)
                    continue

                current_pop = th_data['current_pop']
                max_pop = th_data['max_pop']
                if current_pop is None or max_pop is None:
                    result.update({'status': 'SKIP', 'note': 'Could not read population'})
                    results.append(result)
                    continue
                result['pop'] = f"{current_pop}/{max_pop}"

                tavern_data = self._get_tavern_data(city, tavern)
                if not tavern_data or not tavern_data['action_code']:
                    result.update({'status': 'SKIP', 'note': 'Could not load tavern data'})
                    results.append(result)
                    continue

                if current_pop < max_pop:
                    consumption_values = tavern_data['consumption_values']
                    max_level = max((l for l, w in consumption_values), default=tavern['level'])
                    current_level = tavern_data['current_level']

                    if current_level == max_level:
                        result.update({'status': 'OK', 'note': 'Growing, already MAX'})
                    else:
                        current_wine = self._wine_at_level(consumption_values, current_level)
                        new_wine = self._wine_at_level(consumption_values, max_level)
                        self._apply_level(city, tavern, max_level, tavern_data)
                        result.update({
                            'status': 'CHANGED',
                            'note': f"L{current_level}({current_wine}/h)→L{max_level}({new_wine}/h) [MAX]",
                        })
                    results.append(result)
                    continue

                growth_rate = th_data['growth_rate']
                total_satisfaction = th_data['total_satisfaction']
                result['satisfaction'] = str(total_satisfaction)

                if growth_rate > 0:
                    result.update({'status': 'OK', 'note': f"Growth {growth_rate:+.1f}/h"})
                    results.append(result)
                    continue

                if th_data['resource_shortage']:
                    result.update({'status': 'WARN', 'note': 'Growth=0 due to resource shortage'})
                    results.append(result)
                    continue

                if total_satisfaction < SATISFACTION_BUFFER:
                    result.update({
                        'status': 'WARN',
                        'note': f"Satisfaction {total_satisfaction} below buffer {SATISFACTION_BUFFER}, not reducing wine",
                    })
                    results.append(result)
                    continue

                change = self._optimize_for_satisfaction(city, tavern, tavern_data, total_satisfaction)
                if change:
                    result.update({'status': 'CHANGED', 'note': change})
                else:
                    result.update({'status': 'OK', 'note': 'Already optimal'})

            except Exception as e:
                result.update({'status': 'ERROR', 'note': str(e)})
                if self.notification_mode in (1, 2):
                    sendToBot(self.session, f"❌ Tavern Equilibrium Error\n{city['name']}: {str(e)}")

            results.append(result)

        changes = [r for r in results if r['status'] == 'CHANGED']
        if self.notification_mode == 1 and changes:
            msg = "🍷 Tavern Equilibrium Changes\n\n"
            for r in changes:
                msg += f"📍 {r['name']}: {r['note']}\n"
            sendToBot(self.session, msg)

        return results

    def set_tavern_simple(self, city, percentage):
        city_id = city['id']

        html = self.session.get(city_url + str(city_id))
        city_data = getCity(html)

        tavern = next(
            (b for b in city_data['position'] if b['building'] == 'tavern'),
            None
        )

        if not tavern:
            print(f"  {city['name']}: No tavern")
            return False

        tavern_data = self._get_tavern_data(city, tavern, force_refresh=True)
        if not tavern_data or not tavern_data['action_code']:
            print(f"  {city['name']}: Could not load tavern data")
            return False

        consumption_values = tavern_data['consumption_values']
        current_level = tavern_data['current_level']

        # Calculate the maximum level available in the dropdown
        max_available_level = max((l for l, w in consumption_values), default=0)
        
        # apply the percentage
        target_level = int(max_available_level * (percentage / 100.0))

        current_wine = self._wine_at_level(consumption_values, current_level)
        new_wine = self._wine_at_level(consumption_values, target_level)
        
        if target_level == current_level:
            print(f"  {city['name']}: already at L{current_level}({current_wine}/h)")
            return True
            
        self._apply_level(city, tavern, target_level, tavern_data)
        print(f"  {city['name']}: L{current_level}({current_wine}/h) → L{target_level}({new_wine}/h) ({percentage}%)")
        return True


def _print_results_table(results):
    col_city = max((len(r['name']) for r in results), default=8)
    col_city = max(col_city, 8)

    status_colors = {
        'OK':      bcolors.GREEN,
        'CHANGED': bcolors.BLUE,
        'WARN':    bcolors.WARNING,
        'SKIP':    bcolors.STONE,
        'ERROR':   bcolors.RED,
    }

    header = f"{'City':<{col_city}}  {'Status':<7}  {'Pop':<11}  {'Sat':>5}  Note"
    divider = "─" * (col_city + 7 + 11 + 5 + 4 * 4 + 30)

    print()
    print(header)
    print(divider)

    for r in results:
        color = status_colors.get(r['status'], '')
        status_str = f"{color}{r['status']:<7}{bcolors.ENDC}" if color else f"{r['status']:<7}"
        print(f"{r['name']:<{col_city}}  {status_str}  {r['pop']:<11}  {r['satisfaction']:>5}  {r['note']}")

    print(divider)
    changed = sum(1 for r in results if r['status'] == 'CHANGED')
    ok      = sum(1 for r in results if r['status'] == 'OK')
    warned  = sum(1 for r in results if r['status'] in ('WARN', 'ERROR', 'SKIP'))
    print(
        f"{bcolors.GREEN}{changed} changed{bcolors.ENDC}  "
        f"{ok} ok  "
        f"{bcolors.WARNING}{warned} skipped/warned{bcolors.ENDC}"
    )
    print()


def tavernManager(session, event, stdin_fd, predetermined_input):
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

        print("=" * 60)
        print("ADVANCED TAVERN WINE CONSUMPTION MANAGER")
        print("=" * 60)
        print()
        print("Select operation mode:")
        print()
        print("1. Set tavern level (single city or all cities)")
        print("2. Equilibrium mode (optimize wine usage)")
        print()
        print("(') Back to main menu")

        mode = read(msg="Select mode (1 or 2): ", min=1, max=2, digit=True, additionalValues=["'"])

        if mode == "'":
            event.set()
            return

        print()

        if mode == 1:
            _run_set_mode(session)
        else:
            _run_equilibrium_mode(session, event, stdin_fd, predetermined_input)

    except KeyboardInterrupt:
        pass

    event.set()


def _run_set_mode(session):
    print("=" * 60)
    print("SET TAVERN LEVELS")
    print("=" * 60)
    print()

    print("Which cities?")
    print("1. Single city")
    print("2. All cities")
    print()
    print("(') Back to main menu")
    city_choice = read(msg="Select (1 or 2): ", min=1, max=2, digit=True, additionalValues=["'"])

    if city_choice == "'":
        return

    print()

    if city_choice == 1:
        cities_to_process = [chooseCity(session)]
    else:
        cities_ids, cities = getIdsOfCities(session)
        cities_to_process = [cities[cid] for cid in cities_ids]

    print("Enter the consumption percentage (0-100%):")
    print("e.g., 100 for maximum, 0 for none, 50 for half.")
    percentage = read(msg="Percentage: ", min=0, max=100, digit=True, default=100)
    
    print()
    print(f"Will set {len(cities_to_process)} cities to {percentage}% consumption")
    print()
    print("Proceed? [Y/n]")
    confirm = read(values=["y", "Y", "n", "N", ""])
    if confirm.lower() == "n":
        print("Cancelled.")
        print()
        enter()
        return

    print()
    print("Processing cities...")
    print()

    mgr = TavernManager(session)
    
    success_count = sum(1 for city in cities_to_process if mgr.set_tavern_simple(city, percentage))

    print()
    print(f"{bcolors.GREEN}✓ Complete!{bcolors.ENDC}")
    print(f"Successfully updated {success_count}/{len(cities_to_process)} cities")
    print()
    enter()


def _run_equilibrium_mode(session, event, stdin_fd, predetermined_input):
    print("=" * 60)
    print("EQUILIBRIUM MODE")
    print("=" * 60)
    print()
    print("This mode optimizes wine consumption when population is maxed.")
    print(f"It maintains satisfaction above +{SATISFACTION_BUFFER}.")
    print()

    print("Telegram notifications:")
    print("1. Notify on every change")
    print("2. Notify only on errors")
    print("3. No notifications")
    print()
    print("(') Back to main menu")
    notification_mode = read(msg="Select (1-3): ", min=1, max=3, digit=True, additionalValues=["'"])

    if notification_mode == "'":
        return

    print()

    print("Which cities?")
    print("1. Select specific cities")
    print("2. All cities")
    print()
    print("(') Back to main menu")
    city_choice = read(msg="Select (1 or 2): ", min=1, max=2, digit=True, additionalValues=["'"])

    if city_choice == "'":
        return

    print()

    if city_choice == 1:
        cities_ids, cities = ignoreCities(session, msg="Select cities:")
    else:
        cities_ids, cities = getIdsOfCities(session)

    print("Run mode:")
    print("0. Run once and exit")
    print("1-24. Run continuously, checking every X hours")
    print()
    print("(') Back to main menu")
    run_hours = read(
        msg="Enter hours (0 for once, 1-24 for continuous): ",
        min=0, max=24, digit=True, additionalValues=["'"]
    )

    if run_hours == "'":
        return

    print()

    mgr = TavernManager(session, notification_mode)

    def run_check():
        results = mgr.process_equilibrium(cities_ids, cities)
        _print_results_table(results)
        return results

    if run_hours == 0:
        print(f"Processing {len(cities_ids)} cities...")
        print()
        run_check()
        enter()
        return

    print(f"Will check {len(cities_ids)} cities every {run_hours} hour(s)")
    print("Running first check...")
    print()
    run_check()
    enter()

    set_child_mode(session)
    event.set()

    info = f"\nTavern Equilibrium: {len(cities_ids)} cities, every {run_hours}h\n"
    setInfoSignal(session, info)

    try:
        while True:
            wait(run_hours * 3600)
            run_check()
            session.setStatus(f"Equilibrium check @{getDateTime()}")
    except Exception:
        msg = f"Error in:\n{info}\nCause:\n{traceback.format_exc()}"
        traceback.print_exc()
        if notification_mode in (1, 2):
            sendToBot(session, msg)
    finally:
        session.logout()

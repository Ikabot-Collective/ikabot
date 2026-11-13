#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.market import getGold
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import *

CRYSTAL = 3  # index of crystal in the 5 resource list
FEEDBACK_SUCCESS = 10  # provideFeedback type the game uses for an accepted order


def parseSafehouse(html):
    """Reads what the safehouse view tells about the spies of one city.

    Only markup is used, never translated text, so it works on every server language.

    Parameters
    ----------
    html : str
        the safehouse HTML found in changeView[1][1]

    Returns
    -------
    safehouse : dict
        orderMax : int | None
            the maxValue of the train slider, the most spies one order may ask for right now
        capacity : int | None
            the spies the safehouse can hold
        freeSlots : int | None
            the empty slots, the spies that could still be trained
        goldPerSpy : int | None
        crystalPerSpy : int | None
    """
    safehouse = {
        "orderMax": None,
        "capacity": None,
        "freeSlots": None,
        "goldPerSpy": None,
        "crystalPerSpy": None,
    }
    if not html:
        return safehouse

    # the game leaves the train form out when nothing can be trained (a full safehouse)
    match = re.search(r'id:\s*"slider_spy"\s*,\s*maxValue:\s*(\d+)', html)
    safehouse["orderMax"] = int(match.group(1)) if match else 0

    # <div class="spy_stats_content"><b>{label} 40</b><ul class="disc-list">
    #   <li>{free slots}</li><li>{at home, in defence}</li><li>{on missions}</li></ul></div>
    # the labels are translated, so the numbers are taken by position
    stats = re.search(
        r'class="spy_stats_content"[^>]*>\s*<b>(.*?)</b>\s*<ul[^>]*>(.*?)</ul>',
        html,
        re.DOTALL,
    )
    if stats:
        safehouse["capacity"] = _number(stats.group(1))
        counts = re.findall(r"<li[^>]*>(.*?)</li>", stats.group(2), re.DOTALL)
        if counts:
            safehouse["freeSlots"] = _number(counts[0])

    safehouse["goldPerSpy"] = _number_by_id(html, "js_spygold")
    safehouse["crystalPerSpy"] = _number_by_id(html, "js_spyglass")
    return safehouse


def _number(text):
    """The first whole number in a piece of HTML, thousands separators included"""
    match = re.search(r"\d{1,3}(?:[.,\s\xa0]\d{3})+|\d+", re.sub(r"<[^>]+>", "", text))
    if match is None:
        return None
    return int(re.sub(r"\D", "", match.group(0)))


def _number_by_id(html, element_id):
    match = re.search(r'id="{}"[^>]*>([^<]*)<'.format(element_id), html)
    return _number(match.group(1)) if match else None


def cityNeed(safehouse, target):
    """How many spies one city should be ordered.

    Parameters
    ----------
    safehouse : dict
        as returned by parseSafehouse
    target : int
        0 fills the safehouse, any other value keeps that many spies in the city

    Returns
    -------
    need : int
    """
    capacity = safehouse.get("capacity")
    free = safehouse.get("freeSlots")
    order_max = safehouse.get("orderMax")

    if target <= 0:
        # filling up: the empty slots, or what the slider allows when they are unknown
        need = free if free is not None else order_max
    else:
        if capacity is None or free is None:
            # without knowing how many spies are there, a target cannot be honoured
            return 0
        current = capacity - free
        need = min(target, capacity) - current

    if need is None:
        return 0
    if order_max is not None:
        need = min(need, order_max)
    return max(0, need)


def planSpyTraining(cities, gold, settings):
    """Decides how many spies to order in each city without touching the game.

    Parameters
    ----------
    cities : list[dict]
        one entry per city with a safehouse: id, name, position, crystal (available in the
        city) and safehouse (as returned by parseSafehouse)
    gold : int
        the gold the account has
    settings : dict
        target, goldFloor, crystalFloor and maxPerPass

    Returns
    -------
    (orders, notes) : tuple
        orders is a list of {id, name, position, amount, gold, crystal}, biggest need first;
        notes maps a city name to the reason it got fewer spies than it needs
    """
    gold_budget = max(0, gold - settings["goldFloor"])
    left = settings["maxPerPass"]

    wanted = []
    for city in cities:
        need = cityNeed(city["safehouse"], settings["target"])
        if need > 0:
            wanted.append((need, city))
    wanted.sort(key=lambda w: -w[0])

    orders = []
    notes = {}
    for need, city in wanted:
        gold_per_spy = city["safehouse"].get("goldPerSpy")
        crystal_per_spy = city["safehouse"].get("crystalPerSpy")
        if not gold_per_spy or not crystal_per_spy:
            notes[city["name"]] = "could not read the cost of a spy"
            continue
        if left <= 0:
            notes[city["name"]] = "0/{:d}, spies per pass limit".format(need)
            continue

        spare_crystal = max(0, city["crystal"] - settings["crystalFloor"])
        limits = {
            "spies per pass limit": left,
            "crystal floor": spare_crystal // crystal_per_spy,
            "gold floor": gold_budget // gold_per_spy,
        }
        amount = min(need, *limits.values())
        if amount < need:
            notes[city["name"]] = "{:d}/{:d}, {}".format(
                amount, need, min(limits, key=limits.get)
            )
        if amount <= 0:
            continue

        orders.append(
            {
                "id": city["id"],
                "name": city["name"],
                "position": city["position"],
                "amount": amount,
                "gold": amount * gold_per_spy,
                "crystal": amount * crystal_per_spy,
            }
        )
        gold_budget -= amount * gold_per_spy
        left -= amount

    return orders, notes


def orderAccepted(response):
    """Tells whether the game accepted an order from its AJAX response.

    Parameters
    ----------
    response : list
        the decoded AJAX response

    Returns
    -------
    accepted : bool
    """
    for entry in response:
        if (
            not isinstance(entry, list)
            or len(entry) < 2
            or entry[0] != "provideFeedback"
        ):
            continue
        feedback = entry[1] if isinstance(entry[1], list) else [entry[1]]
        if any(
            isinstance(f, dict) and f.get("type") == FEEDBACK_SUCCESS for f in feedback
        ):
            return True
    return False


class SpyTrainer:
    def __init__(self, session, settings, notification_mode=3):
        self.session = session
        self.settings = settings
        self.notification_mode = notification_mode

    def _read_safehouse(self, city_id, position):
        params = {
            "view": "safehouse",
            "cityId": city_id,
            "position": position,
            "backgroundView": "city",
            "currentCityId": city_id,
            "ajax": "1",
        }
        response = json.loads(self.session.post(params=params), strict=False)
        html = next(
            (
                entry[1][1]
                for entry in response
                if isinstance(entry, list)
                and entry[0] == "changeView"
                and isinstance(entry[1], list)
                and len(entry[1]) > 1
            ),
            "",
        )
        return parseSafehouse(html)

    def _train(self, order):
        params = {
            "action": "Espionage",
            "function": "buildSpy",
            "cityId": order["id"],
            "position": order["position"],
            "textfield_spy": order["amount"],
            "backgroundView": "city",
            "currentCityId": order["id"],
            "templateView": "safehouse",
            "actionRequest": actionRequest,
            "ajax": "1",
        }
        response = json.loads(self.session.post(params=params), strict=False)
        return orderAccepted(response)

    def _gather(self, cities_ids, cities, results):
        """Reads the safehouse of every city, the cities that cannot train go to results"""
        gathered = []
        for city_id in cities_ids:
            name = cities[city_id]["name"]
            try:
                city = getCity(self.session.get(city_url + str(city_id)))
                safehouse = next(
                    (b for b in city["position"] if b["building"] == "safehouse"), None
                )
                if safehouse is None:
                    results.append(
                        {"name": name, "status": "SKIP", "note": "No safehouse"}
                    )
                    continue
                gathered.append(
                    {
                        "id": city_id,
                        "name": name,
                        "position": safehouse["position"],
                        "crystal": city["availableResources"][CRYSTAL],
                        "safehouse": self._read_safehouse(
                            city_id, safehouse["position"]
                        ),
                    }
                )
            except Exception:
                results.append(
                    {
                        "name": name,
                        "status": "ERROR",
                        "note": "Could not read the safehouse",
                    }
                )
        return gathered

    def run_pass(self, cities_ids, cities):
        """Reads every city, plans and sends the orders.

        Returns
        -------
        results : list[dict]
            one {name, status, note} per city
        """
        results = []
        gathered = self._gather(cities_ids, cities, results)
        if not gathered:
            return results

        gold, _ = getGold(self.session, cities[cities_ids[0]])
        orders, notes = planSpyTraining(gathered, gold, self.settings)
        ordered = {order["id"] for order in orders}

        for order in orders:
            note = "{:d} spies ({} gold, {} crystal)".format(
                order["amount"],
                addThousandSeparator(order["gold"]),
                addThousandSeparator(order["crystal"]),
            )
            if order["name"] in notes:
                note += ", " + notes[order["name"]]
            try:
                if self._train(order):
                    results.append(
                        {"name": order["name"], "status": "TRAINED", "note": note}
                    )
                else:
                    results.append(
                        {
                            "name": order["name"],
                            "status": "ERROR",
                            "note": "The game refused the order",
                        }
                    )
            except Exception:
                results.append(
                    {
                        "name": order["name"],
                        "status": "ERROR",
                        "note": "Could not send the order",
                    }
                )

        for city in gathered:
            if city["id"] in ordered:
                continue
            note = notes.get(city["name"], "nothing to train")
            house = city["safehouse"]
            if house.get("capacity") is not None and house.get("freeSlots") is not None:
                note = "{:d}/{:d} spies, {}".format(
                    house["capacity"] - house["freeSlots"], house["capacity"], note
                )
            results.append(
                {
                    "name": city["name"],
                    "status": "OK" if city["name"] not in notes else "WARN",
                    "note": note,
                }
            )

        self._notify(results)
        return results

    def _notify(self, results):
        if self.notification_mode == 3:
            return
        if self.notification_mode == 1:
            shown = [r for r in results if r["status"] in ("TRAINED", "ERROR")]
        else:
            shown = [r for r in results if r["status"] == "ERROR"]
        if not shown:
            return
        msg = "🕵️ Train spies\n\n"
        for r in shown:
            msg += "{} {}: {}\n".format(
                "✅" if r["status"] == "TRAINED" else "❌", r["name"], r["note"]
            )
        sendToBot(self.session, msg)


def _print_results_table(results):
    status_colors = {
        "OK": bcolors.GREEN,
        "TRAINED": bcolors.BLUE,
        "WARN": bcolors.WARNING,
        "SKIP": bcolors.STONE,
        "ERROR": bcolors.RED,
    }
    col_city = max([8] + [len(r["name"]) for r in results])
    print()
    print("{:<{w}}  {:<7}  Note".format("City", "Status", w=col_city))
    print("─" * (col_city + 50))
    for r in results:
        color = status_colors.get(r["status"], "")
        print(
            "{:<{w}}  {}{:<7}{}  {}".format(
                r["name"], color, r["status"], bcolors.ENDC, r["note"], w=col_city
            )
        )
    print()


@task("trainSpies")
def do_trainSpies(session, run_hours, cities_ids, cities, settings, notification_mode):
    trainer = SpyTrainer(session, settings, notification_mode)
    setInfoSignal(
        session,
        "\nTrain spies: {:d} cities, every {:d}h\n".format(len(cities_ids), run_hours),
    )

    while True:
        wait(run_hours * 3600)
        try:
            trainer.run_pass(cities_ids, cities)
        except Exception:
            if notification_mode in (1, 2):
                sendToBot(session, "❌ Train spies\n{}".format(traceback.format_exc()))
        session.setStatus("Spies checked @{}".format(getDateTime()))


@configurator
def trainSpies(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()
    print("Keeps the safehouses trained with spies.\n")

    print("Which cities?")
    print("1. Select specific cities")
    print("2. All cities")
    print("(') Back to main menu")
    choice = read(min=1, max=2, digit=True, additionalValues=["'"])
    if choice == "'":
        return None
    if int(choice) == 1:
        cities_ids, cities = ignoreCities(session, msg="Select cities:")
    else:
        cities_ids, cities = getIdsOfCities(session)

    print("\nHow many spies should each city keep? (0 to fill the safehouse)")
    target = read(min=0, digit=True, default=0)

    print("\nGold to always keep (default 0):")
    gold_floor = read(min=0, digit=True, default=0)

    print("\nCrystal to always keep in each city (default 0):")
    crystal_floor = read(min=0, digit=True, default=0)

    print("\nMost spies ordered in one pass, all cities together (default 100):")
    max_per_pass = read(min=1, digit=True, default=100)

    print("\nTelegram notifications:")
    print("1. Notify on every order")
    print("2. Notify only on errors")
    print("3. No notifications")
    notification_mode = int(read(min=1, max=3, digit=True, default=3))

    print("\nRun mode:")
    print("0. Run once and exit")
    print("1-24. Run continuously, checking every X hours")
    run_hours = read(min=0, max=24, digit=True)

    settings = {
        "target": int(target),
        "goldFloor": int(gold_floor),
        "crystalFloor": int(crystal_floor),
        "maxPerPass": int(max_per_pass),
    }

    print(
        "\nTraining spies in {:d} {}...".format(
            len(cities_ids), "city" if len(cities_ids) == 1 else "cities"
        )
    )
    results = SpyTrainer(session, settings, notification_mode).run_pass(
        cities_ids, cities
    )
    _print_results_table(results)
    enter()

    if int(run_hours) == 0:
        return None

    return {
        "session": session,
        "run_hours": int(run_hours),
        "cities_ids": cities_ids,
        "cities": cities,
        "settings": settings,
        "notification_mode": notification_mode,
    }

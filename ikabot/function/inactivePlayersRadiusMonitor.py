#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import math
import os
import sys
import traceback
from json import JSONDecodeError

import ikabot.config as config
from ikabot.config import city_url, island_url, materials_names_english, miracle_names_english
from ikabot.helpers.botComm import sendToBot, telegramDataIsValid
from ikabot.helpers.getJson import getIsland
from ikabot.helpers.gui import banner, enter
from ikabot.helpers.pedirInfo import chooseCity, read
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import getDateTime, wait

WORLD_MIN = 0
WORLD_MAX = 100
WORLD_CHUNK_SIZE = 50
WORLD_FETCH_RETRIES = 3
WORLD_FETCH_RETRY_WAIT_SECONDS = 2
TELEGRAM_MAX_CHARS = 3500


def inactivePlayersRadiusMonitor(session, event, stdin_fd, predetermined_input):
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
        print("From which city should the inactive-player scan start?")
        start_city = chooseCity(session)

        banner()
        print("Choose the radius to scan around the selected city (0-100).")
        radius = int(read(min=0, max=100, digit=True, default=15))

        banner()
        print("How often should the scan run in hours? (minimum is 1, default is 1)")
        interval_hours = int(read(min=1, digit=True, default=1))

        banner()
        print("Select luxury resource filter:")
        print("(0) Any luxury resource")
        print("(1) Wine")
        print("(2) Marble")
        print("(3) Crystal")
        print("(4) Sulfur")
        luxury_filter = int(read(min=0, max=4, digit=True, default=0))

        banner()
        print("Do you want to send each scan result to Telegram? (Y|N)")
        send_to_telegram = read(values=["y", "Y", "n", "N"], default="n") in ["y", "Y"]
        if send_to_telegram and not telegramDataIsValid(session):
            print("Telegram data is not configured. I will continue without Telegram notifications.")
            send_to_telegram = False

        center_x = int(start_city["x"])
        center_y = int(start_city["y"])

        banner()
        print(
            "Inactive-player monitor configured:\n"
            + "- Center city: {} ({}:{})\n".format(start_city["cityName"], center_x, center_y)
            + "- Radius: {}\n".format(radius)
            + "- Interval: {} hour(s)\n".format(interval_hours)
            + "- Luxury filter: {}\n".format(_luxury_filter_name(luxury_filter))
            + "- Telegram notifications: {}\n".format("Enabled" if send_to_telegram else "Disabled")
            + "\nOnly players in inactive state are shown."
        )
        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nMonitoring inactive players in radius\n"
    setInfoSignal(session, info)
    try:
        do_it(session, center_x, center_y, radius, interval_hours, luxury_filter, send_to_telegram)
    except Exception:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def do_it(session, center_x, center_y, radius, interval_hours, luxury_filter, send_to_telegram):
    """Runs one immediate scan, then repeats on the configured interval."""
    _scan_once(session, center_x, center_y, radius, luxury_filter, send_to_telegram)
    while True:
        wait(interval_hours * 3600)
        _scan_once(session, center_x, center_y, radius, luxury_filter, send_to_telegram)


def _scan_once(session, center_x, center_y, radius, luxury_filter, send_to_telegram):
    islands = _get_islands_in_radius(session, center_x, center_y, radius)
    results = []

    for shallow_island in islands:
        island_id = shallow_island["id"]
        try:
            island = getIsland(session.get(island_url + str(island_id)))
        except Exception:
            continue

        island_x = int(island["x"])
        island_y = int(island["y"])
        distance = _distance(center_x, center_y, island_x, island_y)
        if distance > radius:
            continue
        if luxury_filter != 0 and _island_tradegood(island) != luxury_filter:
            continue

        resource_name = _resource_name(island)
        wonder_name = _wonder_name(island)
        island_name = str(island.get("name", ""))

        for city in island.get("cities", []):
            if city.get("type") == "empty":
                continue
            if city.get("state") != "inactive":
                continue

            results.append(
                {
                    "player": str(city.get("Name", "")),
                    "city": str(city.get("name", "")),
                    "alliance": str(city.get("AllyTag", "-")) or "-",
                    "coords": "{}:{}".format(island_x, island_y),
                    "distance": "{:.2f}".format(distance),
                    "resource": resource_name,
                    "wonder": wonder_name,
                    "island": island_name,
                }
            )

    _print_results(center_x, center_y, radius, luxury_filter, results)

    if send_to_telegram:
        _send_results_to_telegram(session, center_x, center_y, radius, luxury_filter, results)

    status = "Inactive radius monitor center {}:{} radius {} luxury {} -> {} matches @ {}".format(
        center_x,
        center_y,
        radius,
        _luxury_filter_name(luxury_filter),
        len(results),
        getDateTime()[-8:],
    )
    session.setStatus(status)


def _get_islands_in_radius(session, center_x, center_y, radius):
    x_min = max(WORLD_MIN, center_x - radius)
    x_max = min(WORLD_MAX, center_x + radius)
    y_min = max(WORLD_MIN, center_y - radius)
    y_max = min(WORLD_MAX, center_y + radius)

    islands_by_id = {}

    for x_start in range(x_min, x_max + 1, WORLD_CHUNK_SIZE):
        x_end = min(x_start + WORLD_CHUNK_SIZE - 1, x_max)
        for y_start in range(y_min, y_max + 1, WORLD_CHUNK_SIZE):
            y_end = min(y_start + WORLD_CHUNK_SIZE - 1, y_max)
            payload = (
                "action=WorldMap&function=getJSONArea"
                + "&x_min={}&x_max={}&y_min={}&y_max={}".format(x_start, x_end, y_start, y_end)
            )
            data = _get_world_area_data(session, payload)

            for x_key, x_data in data.items():
                for y_key, value in x_data.items():
                    island_id = str(value[0])
                    islands_by_id[island_id] = {
                        "id": island_id,
                        "x": int(x_key),
                        "y": int(y_key),
                    }

    islands = []
    for island in islands_by_id.values():
        if _distance(center_x, center_y, island["x"], island["y"]) <= radius:
            islands.append(island)

    return sorted(islands, key=lambda i: _distance(center_x, center_y, i["x"], i["y"]))


def _print_results(center_x, center_y, radius, luxury_filter, rows):
    banner()
    print("Inactive player scan")
    print(
        "Center: {}:{} | Radius: {} | Luxury: {}".format(
            center_x, center_y, radius, _luxury_filter_name(luxury_filter)
        )
    )

    if not rows:
        print("No inactive players found in the selected radius.")
        return

    table_rows = [
        [
            row["player"],
            row["city"],
            row["alliance"],
            row["coords"],
            row["distance"],
            row["resource"],
            row["wonder"],
            row["island"],
        ]
        for row in rows
    ]

    headers = ["Player", "City", "Ally", "Coords", "Dist", "Resource", "Wonder", "Island"]
    widths = [len(h) for h in headers]

    for row in table_rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    _print_table_line(widths)
    _print_table_row(headers, widths)
    _print_table_line(widths)

    for row in table_rows:
        _print_table_row(row, widths)

    _print_table_line(widths)
    print("Matches: {}".format(len(rows)))


def _print_table_line(widths):
    print("+" + "+".join("-" * (w + 2) for w in widths) + "+")


def _print_table_row(values, widths):
    padded = [" {:<{width}} ".format(value, width=widths[idx]) for idx, value in enumerate(values)]
    print("|" + "|".join(padded) + "|")


def _distance(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _resource_name(island):
    try:
        return materials_names_english[int(island.get("tradegood", 0))]
    except Exception:
        return "Unknown"


def _wonder_name(island):
    if "wonderName" in island and island["wonderName"]:
        return str(island["wonderName"])
    try:
        return miracle_names_english[int(island.get("wonder", 0))]
    except Exception:
        return "Unknown"


def _island_tradegood(island):
    try:
        return int(island.get("tradegood", 0))
    except Exception:
        return 0


def _luxury_filter_name(luxury_filter):
    filter_names = {
        0: "Any",
        1: "Wine",
        2: "Marble",
        3: "Crystal",
        4: "Sulfur",
    }
    return filter_names.get(luxury_filter, "Any")


def _send_results_to_telegram(session, center_x, center_y, radius, luxury_filter, rows):
    header = (
        "Inactive player scan\n"
        + "Center: {}:{}\n".format(center_x, center_y)
        + "Radius: {}\n".format(radius)
        + "Luxury: {}\n".format(_luxury_filter_name(luxury_filter))
        + "Matches: {}\n".format(len(rows))
    )

    if not rows:
        sendToBot(session, header + "\nNo inactive players found.")
        return

    lines = []
    for idx, row in enumerate(rows, start=1):
        lines.append(
            "{}. {} | {} | {} | {} | d={} | {} | {}".format(
                idx,
                row["player"],
                row["city"],
                row["coords"],
                row["alliance"],
                row["distance"],
                row["resource"],
                row["wonder"],
            )
        )

    _send_text_in_chunks(session, header + "\n" + "\n".join(lines))


def _send_text_in_chunks(session, text):
    text = text.strip()
    if not text:
        return

    start = 0
    while start < len(text):
        end = min(start + TELEGRAM_MAX_CHARS, len(text))
        if end < len(text):
            split_idx = text.rfind("\n", start, end)
            if split_idx > start:
                end = split_idx
        chunk = text[start:end].strip()
        if chunk:
            sendToBot(session, chunk)
        start = end


def _get_world_area_data(session, payload):
    """Returns world-map area data while handling transient invalid responses."""
    for _ in range(WORLD_FETCH_RETRIES):
        try:
            response = session.post(payload)
            parsed = _safe_json_parse(response)
            if isinstance(parsed, dict) and "data" in parsed and isinstance(parsed["data"], dict):
                return parsed["data"]
        except Exception:
            pass
        wait(WORLD_FETCH_RETRY_WAIT_SECONDS)
    return {}


def _safe_json_parse(raw):
    """Parses JSON even when responses are bytes or prefixed by anti-CSRF guards."""
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")

    raw = str(raw).strip()
    if not raw:
        return {}

    # Some endpoints may include a non-JSON prefix (e.g. while(1);)
    for marker in ["{", "["]:
        idx = raw.find(marker)
        if idx != -1:
            candidate = raw[idx:]
            try:
                return json.loads(candidate)
            except JSONDecodeError:
                continue

    return {}

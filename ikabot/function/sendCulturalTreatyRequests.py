#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import json
import os
import re
import sys
import time
import traceback

import ikabot.config as config
from ikabot.config import actionRequest, island_url
from ikabot.helpers.getJson import getCity, getIsland, getWorldMapIslands
from ikabot.helpers.gui import banner
from ikabot.helpers.pedirInfo import getIdsOfCities, read
from ikabot.helpers.process import set_child_mode, updateProcessList
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import getCurrentCityId, wait


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _update_task_status(session, status):
    """Update current process status in ikabot process list."""
    try:
        pid = os.getpid()
        process_list = updateProcessList(session)
        found = False
        for process in process_list:
            if process.get("pid") == pid:
                process["status"] = status
                found = True
                break

        if not found:
            process_list.append(
                {
                    "pid": pid,
                    "action": "sendCulturalTreatyRequests",
                    "date": time.time(),
                    "status": status,
                }
            )

        session_data = session.getSessionData()
        session_data["processList"] = process_list
        session.setSessionData(session_data)
    except Exception:
        pass


def _parse_message_datetime(date_text):
    """Parse a message date string into a unix timestamp, if possible."""
    if not date_text:
        return None

    text = re.sub(r"\s+", " ", str(date_text)).strip()
    if not text:
        return None

    now = datetime.datetime.now()
    low = text.lower()

    # Relative formats like "Today 14:32" / "Danas 14:32"
    time_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", text)
    if time_match:
        hms = time_match.group(1)
        if "today" in low or "danas" in low:
            for fmt in ["%H:%M:%S", "%H:%M"]:
                try:
                    parsed_time = datetime.datetime.strptime(hms, fmt).time()
                    dt = datetime.datetime.combine(now.date(), parsed_time)
                    return dt.timestamp()
                except Exception:
                    pass
        if "yesterday" in low or "jučer" in low or "jucer" in low:
            for fmt in ["%H:%M:%S", "%H:%M"]:
                try:
                    parsed_time = datetime.datetime.strptime(hms, fmt).time()
                    dt = datetime.datetime.combine(
                        now.date() - datetime.timedelta(days=1), parsed_time
                    )
                    return dt.timestamp()
                except Exception:
                    pass

    patterns = [
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%y %H:%M:%S",
        "%d.%m.%y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
    ]

    for fmt in patterns:
        try:
            return datetime.datetime.strptime(text, fmt).timestamp()
        except Exception:
            pass

    # Pattern without year, assume current year.
    for fmt in ["%d.%m. %H:%M:%S", "%d.%m. %H:%M"]:
        try:
            dt = datetime.datetime.strptime(text, fmt)
            dt = dt.replace(year=now.year)
            return dt.timestamp()
        except Exception:
            pass

    return None


def _extract_change_view_html(raw, view_name=None):
    """Extract HTML payload from an Ikariam ajax response."""
    if not raw:
        return ""

    html_content = raw
    try:
        data = json.loads(raw)
        for item in data:
            if not (
                isinstance(item, list) and len(item) >= 2 and item[0] == "changeView"
            ):
                continue
            inner = item[1]
            if not (isinstance(inner, list) and len(inner) >= 2):
                continue
            if view_name is None or inner[0] == view_name:
                return str(inner[1])
    except Exception:
        pass
    return html_content


def _extract_outbox_timestamps(raw):
    """Parse outgoing message timestamps from diplomacyAdvisorOutBox response."""
    html_content = _extract_change_view_html(raw, "diplomacyAdvisorOutBox")
    if not html_content:
        return []

    timestamps = []
    for row_match in re.finditer(
        r'<tr[^>]*id=["\']?message\d+["\']?[^>]*>([\s\S]*?)</tr>',
        html_content,
        flags=re.IGNORECASE,
    ):
        row_html = row_match.group(1)

        date_match = re.search(
            r"<td[^>]*>\s*([^<]*\d{1,2}\.\d{1,2}\.\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?)\s*</td>\s*$",
            row_html,
            flags=re.IGNORECASE,
        )
        if date_match is None:
            td_matches = list(
                re.finditer(r"<td[^>]*>([\s\S]*?)</td>", row_html, flags=re.IGNORECASE)
            )
            if not td_matches:
                continue
            date_text = re.sub(r"<[^>]+>", "", td_matches[-1].group(1)).strip()
        else:
            date_text = re.sub(r"<[^>]+>", "", date_match.group(1)).strip()

        timestamp = _parse_message_datetime(date_text)
        if timestamp is not None:
            timestamps.append(float(timestamp))

    return sorted(set(timestamps), reverse=True)


def _fetch_outbox_data(session, city_id):
    """
    Fetch diplomacyAdvisorOutBox and return all parsed outgoing timestamps.
    """
    try:
        url = "view=diplomacyAdvisorOutBox&backgroundView=city&currentCityId={}&templateView=diplomacyAdvisor&actionRequest={}&ajax=1".format(
            city_id, actionRequest
        )
        raw = session.get(url)
        if not raw:
            return []
        return _extract_outbox_timestamps(raw)
    except Exception:
        return []


def _fetch_pending_museum_requests(session, city_id, museum_position):
    """
    Fetch pending treaty requests from museum view with pagination.
    Returns a set of player names that have pending requests.
    """
    pending_players = set()
    page = 0

    while True:
        try:
            query = (
                "view=museum&cityId={cid}&position={pos}"
                "&backgroundView=city&currentCityId={cid}"
                "&actionRequest={ar}&ajax=1"
            ).format(cid=city_id, pos=museum_position, ar=actionRequest)

            if page > 0:
                query += "&requestsPage={}".format(page)

            raw = session.get(query)
            if not raw:
                break

            html_content = _extract_change_view_html(raw, "museum")

            # Extract player names from the pending requests table
            # Format: <td class="player center">Player Name</td>
            page_players = re.findall(
                r'<td\s+class=["\']player\s+center["\'][^>]*>([\s\S]*?)</td>',
                html_content,
                flags=re.IGNORECASE,
            )

            if not page_players:
                break

            for player_html in page_players:
                # Extract plain text from HTML (remove any tags)
                player_name = re.sub(r"<[^>]+>", "", player_html).strip()
                if player_name:
                    pending_players.add(player_name)

            # Check if there's a next page by looking for the next page link
            if "requestsPage={}".format(page + 1) not in html_content:
                break

            page += 1
        except Exception:
            break

    return pending_players


def _fetch_recent_outgoing_timestamps(session, city_id, window_seconds):
    """
    Fetch outgoing message timestamps from diplomacyAdvisorOutBox.
    Returns timestamps of messages within the given time window (in seconds).
    """
    now = time.time()
    timestamps = _fetch_outbox_data(session, city_id)
    return [t for t in timestamps if 0 <= now - t <= window_seconds]


def _fetch_last_outgoing_timestamp(session, city_id):
    """Return the newest parsed timestamp from the outbox, if available."""
    timestamps = _fetch_outbox_data(session, city_id)
    if not timestamps:
        return None
    return max(timestamps)


def _merge_outgoing_timestamps(
    outbox_timestamps, local_bot_timestamps, tolerance_seconds=10
):
    """Merge outgoing timestamps without double-counting bot sends already visible in outbox."""
    merged = list(outbox_timestamps)
    unmatched_local = []

    for bot_timestamp in local_bot_timestamps:
        if any(
            abs(outbox_timestamp - bot_timestamp) <= tolerance_seconds
            for outbox_timestamp in outbox_timestamps
        ):
            continue
        merged.append(bot_timestamp)
        unmatched_local.append(bot_timestamp)

    return merged, unmatched_local


def _get_city_info(session):
    """
    Return (city_id, museum_position), preferring the current city.
    museum_position is the index in the city's position array, or None if
    the city has no museum.
    """
    city_id = None
    try:
        city_id = str(getCurrentCityId(session))
    except Exception:
        city_ids, _ = getIdsOfCities(session)
        if city_ids:
            city_id = str(city_ids[0])

    if city_id is None:
        return None, None

    try:
        html = session.get(config.city_url + city_id)
        city = getCity(html)
        for i, building in enumerate(city.get("position", [])):
            if building.get("building") == "museum" or building.get("buildingId") == 10:
                return city_id, i
    except Exception:
        pass
    return city_id, None


def _fetch_existing_treaty_player_ids(session, city_id, museum_position):
    """
    Return the set of player IDs (strings) that already have a confirmed
    cultural treaty with the current player.

    Uses view=museumTreaties, which returns a JSON envelope wrapping HTML.
    Treaty partners appear as cancelTreaty links:
      href="?view=sendIKMessage&receiverId=XXXXX&msgType=81"
    Handles pagination automatically.
    """
    treaty_ids = set()
    page = 0
    while True:
        try:
            query = (
                "view=museumTreaties&activeTab=tab_museumTreaties"
                "&cityId={cid}&position={pos}"
                "&backgroundView=city&currentCityId={cid}"
                "&templateView=culturalPossessions_assign"
                "&currentTab=tab_culturalPossessions_assign"
                "&actionRequest={ar}&ajax=1"
            ).format(cid=city_id, pos=museum_position, ar=actionRequest)
            if page > 0:
                query += "&treatiesPage={}".format(page)

            raw = session.get(query)
            if not raw:
                break

            html_content = _extract_change_view_html(raw, "museumTreaties")

            # cancelTreaty links use msgType=81; extract their receiverId
            page_ids = re.findall(r'receiverId=(\d+)[^"]*msgType=81', html_content)
            if not page_ids:
                break
            treaty_ids.update(page_ids)

            # Follow next page if it exists
            if "treatiesPage={}".format(page + 1) not in html_content:
                break
            page += 1
        except Exception:
            break
    return treaty_ids


def _get_search_centers(session):
    """Return unique (x, y) island coordinates of the user's cities."""
    own_city_ids, _ = getIdsOfCities(session)
    centers = set()
    for city_id in own_city_ids:
        try:
            html = session.get(config.city_url + str(city_id))
            city = getCity(html)
            centers.add((int(city["x"]), int(city["y"])))
        except Exception:
            pass
    return sorted(centers)


def _get_world_islands_sorted_by_radius(session, centers):
    """
    Fetch worldmap shallow island data and sort islands by nearest
    distance to any of the provided centers.
    """
    if not centers:
        return []

    world_islands = []
    for x_min, x_max, y_min, y_max in [
        (0, 50, 0, 50),
        (50, 100, 0, 50),
        (0, 50, 50, 100),
        (50, 100, 50, 100),
    ]:
        try:
            data = session.post(
                "action=WorldMap&function=getJSONArea&x_min={}&x_max={}&y_min={}&y_max={}".format(
                    x_min, x_max, y_min, y_max
                )
            )
            world_islands.extend(getWorldMapIslands(data))
        except Exception:
            pass

    def min_distance(island):
        x = int(island["x"])
        y = int(island["y"])
        return min(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for cx, cy in centers)

    world_islands.sort(key=min_distance)
    return world_islands


def _get_candidate_players(
    session, own_username, required_count, excluded_ids, pending_players
):
    """
    Scan islands around user's cities, expanding outward by radius until
    enough valid candidates are found.

    Returns a dict: {player_id_str: {"playerName": str, "cityName": str}}
    """
    centers = _get_search_centers(session)
    islands = _get_world_islands_sorted_by_radius(session, centers)
    candidates = {}
    scanned_islands = 0

    for island_info in islands:
        island_id = str(island_info["id"])
        island_x = island_info.get("x", "?")
        island_y = island_info.get("y", "?")

        try:
            html = session.get(island_url + island_id)
            island = getIsland(html)
        except Exception:
            continue
        scanned_islands += 1
        print("Searching island at coordinates ({}, {})...".format(island_x, island_y))

        for city in island.get("cities", []):
            if city.get("type") in ("empty", "buildplace"):
                continue
            player_name = city.get("Name") or city.get("ownerName") or ""
            if player_name == own_username:
                continue
            player_id = str(city.get("Id") or city.get("ownerId") or "")
            if not player_id or player_id == "0":
                continue
            if player_id not in candidates:
                candidates[player_id] = {
                    "playerName": player_name,
                    "cityName": city.get("name") or "",
                }

        # Count valid candidates (not in excluded_ids and not in pending_players)
        valid_candidates = [
            pid
            for pid in candidates
            if pid not in excluded_ids
            and candidates[pid]["playerName"] not in pending_players
        ]

        # Stop once we have enough valid candidates.
        if len(valid_candidates) >= required_count:
            break

    print("Scanned {} island(s) while expanding search radius.".format(scanned_islands))
    return candidates


# ---------------------------------------------------------------------------
# Treaty request sender
# ---------------------------------------------------------------------------


def _send_treaty_request(session, current_city_id, target_player_id):
    """
    Send a cultural treaty request to the target player.

    Ikariam implements this as a special in-game message with msgType=77.
    Captured from DevTools:
      action=Messages&function=send&receiverId=<id>&msgType=77&content=
      &isMission=0&closeView=0&allyId=0&backgroundView=city
      &currentCityId=<id>&templateView=sendIKMessage&actionRequest=<ar>&ajax=1

    Returns True on success, False otherwise.
    """
    params = {
        "action": "Messages",
        "function": "send",
        "receiverId": target_player_id,
        "msgType": "77",
        "content": "",
        "isMission": "0",
        "closeView": "0",
        "allyId": "0",
        "backgroundView": "city",
        "currentCityId": current_city_id,
        "templateView": "sendIKMessage",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    try:
        session.post(params=params)
        return True
    except Exception:
        print(
            "  Error sending request to player {}: {}".format(
                target_player_id, traceback.format_exc()
            )
        )
        return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def sendCulturalTreatyRequests(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd : int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input

    try:
        banner()
        print(
            "This feature sends cultural treaty requests to players around your cities"
        )
        print("that you don't already have a cultural treaty with.")
        print()

        print("How many treaty requests should I send? (min: 1)")
        count = int(read(min=1, digit=True))

        banner()
        print("Delay between requests in seconds? (min: 1, default: 5)")
        delay = int(read(min=1, digit=True, default=5))

        banner()
        set_child_mode(session)
        event.set()
        setInfoSignal(session, "Sending cultural treaty requests")
        _update_task_status(session, "running - preparing")

        print("Fetching own city and museum position...")
        _update_task_status(session, "running - locating museum")
        city_id, museum_position = _get_city_info(session)
        if city_id is None:
            _update_task_status(session, "failed - no city id")
            print("Could not determine own city ID. Aborting.")
            return
        if museum_position is None:
            _update_task_status(session, "failed - no museum found")
            print("No museum found in your first city. Aborting.")
            return

        print("Fetching existing treaties...")
        _update_task_status(session, "running - fetching treaties")
        existing_ids = _fetch_existing_treaty_player_ids(
            session, city_id, museum_position
        )
        print("Found {} existing treaties.".format(len(existing_ids)))

        # Fetch pending requests from museum with pagination
        print("Checking for pending requests...")
        pending_museum = _fetch_pending_museum_requests(
            session, city_id, museum_position
        )
        print("Found {} pending requests in museum.".format(len(pending_museum)))

        # Build exclusion set: confirmed treaties
        excluded_ids = set(existing_ids)

        print("\nScanning islands in expanding radius for candidate players...")
        _update_task_status(session, "running - scanning candidates")
        own_username = session.username
        candidates = _get_candidate_players(
            session, own_username, count, excluded_ids, pending_museum
        )
        print("Found {} candidate player(s).".format(len(candidates)))

        # Build final list of valid candidates (excluding confirmed treaties and pending requests)
        new_candidates = [
            (pid, info)
            for pid, info in candidates.items()
            if pid not in excluded_ids and info.get("playerName") not in pending_museum
        ]
        print(
            "Valid candidate(s) ready to send requests: {}".format(len(new_candidates))
        )

        if not new_candidates:
            _update_task_status(session, "finished - no new candidates")
            print("No new candidates found. Nothing to do.")
            return

        to_send = new_candidates[:count]
        print("\nSending {} cultural treaty request(s)...\n".format(len(to_send)))

        sent = 0
        failed = 0

        RATE_LIMIT = 5  # server cap: 5 outgoing messages
        RATE_WINDOW = 5 * 60  # per 5 minutes
        RESERVED_FOR_USER = 1  # keep one slot free for manual user messages
        BOT_BUDGET = max(1, RATE_LIMIT - RESERVED_FOR_USER)
        bot_send_timestamps = []

        initial_recent_outgoing = _fetch_recent_outgoing_timestamps(
            session, city_id, RATE_WINDOW
        )
        last_outgoing = _fetch_last_outgoing_timestamp(session, city_id)
        if last_outgoing is not None:
            last_outgoing_str = datetime.datetime.fromtimestamp(last_outgoing).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            print(
                "Latest outgoing message detected at {}. Outbox shows {} outgoing message(s) in the last 5 minutes.".format(
                    last_outgoing_str,
                    len(initial_recent_outgoing),
                )
            )
        else:
            print(
                "Could not determine the last outgoing message time. Outbox shows {} outgoing message(s) in the last 5 minutes, so pacing stays enabled because the server allows only {} outgoing messages per 5 minutes and the bot reserves {} slot for manual use.".format(
                    len(initial_recent_outgoing),
                    RATE_LIMIT,
                    RESERVED_FOR_USER,
                )
            )

        for i, (player_id, info) in enumerate(to_send, start=1):
            _update_task_status(
                session,
                "running - sending {}/{}".format(i, len(to_send)),
            )

            while True:
                now = time.time()

                # Refresh user outbox before each send so manual messages are accounted for.
                recent_outbox = _fetch_recent_outgoing_timestamps(
                    session, city_id, RATE_WINDOW
                )
                recent_outbox = [t for t in recent_outbox if now - t < RATE_WINDOW]
                bot_send_timestamps = [
                    t for t in bot_send_timestamps if now - t < RATE_WINDOW
                ]

                merged_outgoing, unmatched_bot_timestamps = _merge_outgoing_timestamps(
                    recent_outbox,
                    bot_send_timestamps,
                )

                total_recent_outgoing = len(merged_outgoing)
                available_for_bot = BOT_BUDGET - total_recent_outgoing
                if available_for_bot > 0:
                    break

                if not merged_outgoing:
                    # Fallback safety net; should rarely happen.
                    wait_seconds = RATE_WINDOW
                else:
                    earliest_expiry = min(merged_outgoing) + RATE_WINDOW
                    wait_seconds = max(1, int(earliest_expiry - now) + 1)

                _update_task_status(
                    session,
                    "running - waiting outbox window ({}s)".format(wait_seconds),
                )
                print(
                    "  [Outbox pacing] Waiting {}s because {} outgoing message(s) were detected in the last 5 minutes. The server limit is {} per 5 minutes, and the bot keeps {} slot free for manual use.".format(
                        wait_seconds,
                        total_recent_outgoing,
                        RATE_LIMIT,
                        RESERVED_FOR_USER,
                    )
                )
                wait(wait_seconds)

            print(
                "[{}/{}] Sending request to {} ({})...".format(
                    i,
                    len(to_send),
                    info["playerName"],
                    info["cityName"],
                )
            )
            success = _send_treaty_request(session, city_id, player_id)
            if success:
                sent += 1
                bot_send_timestamps.append(time.time())
                print("  -> Sent.")
            else:
                failed += 1
                print("  -> Failed.")

            if i < len(to_send):
                wait(delay, maxrandom=2)

        _update_task_status(
            session,
            "finished - sent {} failed {}".format(sent, failed),
        )
        print("\nDone. Sent: {}  Failed: {}".format(sent, failed))

    except KeyboardInterrupt:
        _update_task_status(session, "stopped")
        pass
    except Exception:
        _update_task_status(session, "failed")
        print(traceback.format_exc())

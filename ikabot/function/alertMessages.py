#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import hashlib
import html
import os
import re
import sys
import time
import traceback

import ikabot.config as config
from ikabot.helpers.botComm import checkTelegramData, sendToBot
from ikabot.helpers.gui import banner, enter
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import addThousandSeparator, daysHoursMinutes


POLL_MINUTES_DEFAULT = 10

TYPE_LABELS = {
    "player": "Player messages",
    "combat": "Combat reports",
}


def _format_runtime_summary(
    interval_minutes,
    enabled_types,
    include_battlefield_details,
    notify_existing,
    include_movements,
    movement_interval_minutes,
):
    return (
        "Interval: {} minute(s)\n".format(interval_minutes)
        + "Types: {}\n".format(_format_enabled_types(enabled_types))
        + "Battlefield details: {}\n".format("Enabled" if include_battlefield_details else "Disabled")
        + "Notify existing on first scan: {}\n".format("Yes" if notify_existing else "No")
        + "Movement reports: {}".format(
            "Every {} minute(s)".format(movement_interval_minutes) if include_movements else "Disabled"
        )
    )


def alertMessages(session, event, stdin_fd, predetermined_input):
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
        if checkTelegramData(session) is False:
            event.set()
            return

        banner()
        print("How often should I check in-game messages in minutes? (min:1, default: 10)")
        interval_minutes = int(read(min=1, digit=True, default=POLL_MINUTES_DEFAULT))

        banner()
        print("Select which message types should trigger Telegram alerts:")
        print("(1) All")
        print("(2) Player messages")
        print("(3) Combat reports")
        print("Type one or more numbers separated by commas (example: 2,3). Default: 1")
        raw_selection = str(read(empty=True, default="1")).strip()
        enabled_types = _parse_type_selection(raw_selection)

        banner()
        print("Include detailed battlefield info for combat reports? (y|N)")
        include_battlefield_details = read(values=["y", "Y", "n", "N"], default="n") in ["y", "Y"]

        banner()
        print("Should already existing messages trigger alerts on first scan? (y|N)")
        notify_existing = read(values=["y", "Y", "n", "N"], default="n") in ["y", "Y"]

        banner()
        print("Also send military movement reports to Telegram? (y|N)")
        include_movements = read(values=["y", "Y", "n", "N"], default="n") in ["y", "Y"]

        movement_interval_minutes = 0
        if include_movements:
            banner()
            print("How often should I send movement reports in minutes? (min:1, default: 10)")
            movement_interval_minutes = int(read(min=1, digit=True, default=POLL_MINUTES_DEFAULT))

        print(
            "Message alert configured:\n"
            + "- "
            + _format_runtime_summary(
                interval_minutes,
                enabled_types,
                include_battlefield_details,
                notify_existing,
                include_movements,
                movement_interval_minutes,
            ).replace("\n", "\n- ")
        )
        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nI check in-game messages every {} minute(s)\n".format(interval_minutes)
    setInfoSignal(session, info)

    try:
        do_it(
            session,
            interval_minutes,
            enabled_types,
            notify_existing,
            include_battlefield_details,
            include_movements,
            movement_interval_minutes,
        )
    except Exception:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def do_it(
    session,
    interval_minutes,
    enabled_types,
    notify_existing,
    include_battlefield_details,
    include_movements,
    movement_interval_minutes,
):
    known_message_ids = set()
    last_unread_count = _fetch_unread_count(session)
    last_estimated_count = _estimate_message_count(session)
    next_message_check = time.time()
    next_movement_check = time.time() if include_movements else None

    sendToBot(
        session,
        "-- MESSAGE ALERTS STARTED --\n"
        + _format_runtime_summary(
            interval_minutes,
            enabled_types,
            include_battlefield_details,
            notify_existing,
            include_movements,
            movement_interval_minutes,
        ),
    )

    initial_messages = _fetch_messages(session)
    if notify_existing:
        to_notify = _filter_messages(initial_messages, enabled_types)
        if include_battlefield_details:
            _enrich_combat_details(session, to_notify)
        _notify_messages(session, to_notify)
        if not to_notify and (last_unread_count or 0) > 0:
            _notify_unparsed_count(session, last_unread_count)
        elif not to_notify and (last_estimated_count or 0) > 0:
            _notify_unparsed_count(session, last_estimated_count)
    known_message_ids.update(m["id"] for m in initial_messages)

    while True:
        now = time.time()

        if now >= next_message_check:
            last_unread_count, last_estimated_count = _poll_once(
                session,
                known_message_ids,
                enabled_types,
                include_battlefield_details,
                last_unread_count,
                last_estimated_count,
            )
            next_message_check = now + interval_minutes * 60

        if include_movements and next_movement_check is not None and now >= next_movement_check:
            _notify_movement_report(session)
            next_movement_check = now + movement_interval_minutes * 60

        wait_targets = [next_message_check]
        if include_movements and next_movement_check is not None:
            wait_targets.append(next_movement_check)
        sleep_seconds = max(1, int(min(wait_targets) - time.time()))
        time.sleep(sleep_seconds)


def _poll_once(
    session,
    known_message_ids,
    enabled_types,
    include_battlefield_details,
    last_unread_count,
    last_estimated_count,
):
    messages = _fetch_messages(session)
    new_messages = [m for m in messages if m["id"] not in known_message_ids]
    known_message_ids.update(m["id"] for m in messages)

    to_notify = _filter_messages(new_messages, enabled_types)
    if include_battlefield_details:
        _enrich_combat_details(session, to_notify)
    _notify_messages(session, to_notify)

    current_unread_count = _fetch_unread_count(session)
    if (
        current_unread_count is not None
        and last_unread_count is None
        and current_unread_count > 0
        and not to_notify
    ):
        _notify_unparsed_count(session, current_unread_count)
    if (
        current_unread_count is not None
        and last_unread_count is not None
        and current_unread_count > last_unread_count
        and not to_notify
    ):
        _notify_unparsed_count(session, current_unread_count - last_unread_count)
    if current_unread_count is not None:
        last_unread_count = current_unread_count

    current_estimated_count = _estimate_message_count(session)
    if (
        current_estimated_count is not None
        and last_estimated_count is not None
        and current_estimated_count > last_estimated_count
        and not to_notify
        and current_unread_count is None
    ):
        _notify_unparsed_count(session, current_estimated_count - last_estimated_count)
    if current_estimated_count is not None:
        last_estimated_count = current_estimated_count

    session.setStatus(
        "Message alerts: {} known, {} matched, unread {}, est {}".format(
            len(known_message_ids),
            len(to_notify),
            "?" if last_unread_count is None else last_unread_count,
            "?" if last_estimated_count is None else last_estimated_count,
        )
    )

    return last_unread_count, last_estimated_count


def _fetch_messages(session):
    """Fetch mailbox data from both page HTML and advisor AJAX payloads."""
    merged = {}

    def quality_score(message):
        score = 0
        if str(message.get("sender", "")).strip().lower() not in ["", "unknown sender"]:
            score += 1
        if str(message.get("subject", "")).strip().lower() not in ["", "no subject"]:
            score += 1
        if str(message.get("body", "")).strip() != "":
            score += 2
        if str(message.get("type", "unknown")).strip().lower() != "unknown":
            score += 1
        return score

    for payload in _fetch_message_payloads(session):
        for candidate in _payload_variants(payload):
            parsed = _parse_messages_from_payload(candidate)
            for message in parsed:
                msg_id = _canonical_message_id(message.get("id", ""))
                if not msg_id:
                    continue
                message["id"] = msg_id
                prev = merged.get(msg_id)
                if prev is None or quality_score(message) > quality_score(prev):
                    merged[msg_id] = message

    for message in _fetch_combat_reports(session):
        msg_id = _canonical_message_id(message.get("id", ""))
        if not msg_id:
            continue
        message["id"] = msg_id
        prev = merged.get(msg_id)
        if prev is None or quality_score(message) > quality_score(prev):
            merged[msg_id] = message

    return list(merged.values())


def _fetch_combat_reports(session):
    payloads = []

    city_id = None
    try:
        html_home = session.get()
        match = re.search(r"currentCityId:\s*(\d+),", html_home)
        if match:
            city_id = match.group(1)
    except Exception:
        pass

    html_urls = [
        "view=militaryAdvisorCombatList",
        "view=militaryAdvisorCombatList&activeTab=tab_militaryAdvisorCombatList",
    ]
    if city_id is not None:
        html_urls.append(
            "view=militaryAdvisorCombatList&activeTab=tab_militaryAdvisorCombatList&backgroundView=city&currentCityId={}".format(
                city_id
            )
        )

    for url in html_urls:
        try:
            data = session.get(url)
            if data:
                payloads.append(str(data))
        except Exception:
            continue

    if city_id is not None:
        ajax_urls = [
            (
                "view=militaryAdvisorCombatList&oldView=city&oldBackgroundView=city&backgroundView=city"
                "&currentCityId={}&templateView=militaryAdvisorCombatList&actionRequest={}"
                "&activeTab=tab_militaryAdvisorCombatList&ajax=1"
            ).format(city_id, config.actionRequest),
            (
                "view=militaryAdvisorCombatList&backgroundView=city&currentCityId={}&actionRequest={}"
                "&activeTab=tab_militaryAdvisorCombatList&ajax=1"
            ).format(city_id, config.actionRequest),
        ]

        for url in ajax_urls:
            raw = None
            try:
                raw = session.post(url)
            except Exception:
                try:
                    raw = session.get(url)
                except Exception:
                    raw = None
            if raw:
                payloads.append(str(raw))
                payloads.extend(_extract_ajax_html_fragments(raw))
                payloads.extend(_flatten_json_payload(raw))

    merged = {}
    for payload in payloads:
        for candidate in _payload_variants(payload):
            for report in _parse_combat_reports_from_payload(candidate):
                cid = report.get("id", "")
                if not cid:
                    continue
                prev = merged.get(cid)
                if prev is None:
                    merged[cid] = report
                    continue
                # Prefer richer versions that include more filled fields.
                prev_score = int(bool(prev.get("subject"))) + int(bool(prev.get("town"))) + int(bool(prev.get("date")))
                score = int(bool(report.get("subject"))) + int(bool(report.get("town"))) + int(bool(report.get("date")))
                if score > prev_score:
                    merged[cid] = report

    return list(merged.values())


def _parse_combat_reports_from_payload(payload):
    reports = []

    row_pattern = re.compile(
        r'<tr[^>]*class=["\']([^"\']*)["\'][^>]*>([\s\S]*?)</tr>',
        flags=re.IGNORECASE,
    )

    for row_match in row_pattern.finditer(payload):
        row_class = row_match.group(1).lower()
        row_html = row_match.group(2)
        combat_id = _extract_combat_id_from_row(row_html)
        if combat_id is None:
            continue
        battle_type = _clean_text(
            re.search(r'<img[^>]*title=["\']([^"\']+)["\']', row_html, flags=re.IGNORECASE).group(1)
        ) if re.search(r'<img[^>]*title=["\']([^"\']+)["\']', row_html, flags=re.IGNORECASE) else "Combat"

        date_match = re.search(r'<td[^>]*class=["\'][^"\']*date[^"\']*["\'][^>]*>([\s\S]*?)</td>', row_html, flags=re.IGNORECASE)
        date = _clean_text(date_match.group(1)) if date_match else ""

        rounds = ""
        right_cells = re.findall(r'<td[^>]*class=["\'][^"\']*right[^"\']*["\'][^>]*>([\s\S]*?)</td>', row_html, flags=re.IGNORECASE)
        if right_cells:
            rounds = _clean_text(right_cells[0])

        left_cells = re.findall(r'<td[^>]*class=["\'][^"\']*left[^"\']*["\'][^>]*>([\s\S]*?)</td>', row_html, flags=re.IGNORECASE)
        town = _clean_text(left_cells[1]) if len(left_cells) >= 2 else ""
        owner = _clean_text(left_cells[2]) if len(left_cells) >= 3 else ""

        # Some servers use classes beyond red/green (or no color markers). Keep report anyway.
        if "running" in row_html.lower() and "bold" in row_html.lower():
            outcome = "Ongoing"
        elif "green" in row_class:
            outcome = "Win"
        elif "red" in row_class:
            outcome = "Loss"
        else:
            outcome = "Unknown"
        subject = battle_type
        if town:
            subject = "{} | {}".format(battle_type, town)

        body_parts = ["Outcome: {}".format(outcome)]
        if rounds:
            body_parts.append("Rounds: {}".format(rounds))
        if owner:
            body_parts.append("Owner: {}".format(owner))

        reports.append(
            {
                "id": _compose_combat_message_id(combat_id, date, rounds),
                "type": "combat",
                "sender": owner if owner else "Combat report",
                "subject": subject,
                "outcome": outcome,
                "round": rounds,
                "body": ", ".join(body_parts),
                "town": town,
                "date": date,
                "combat_id": combat_id,
            }
        )

    return reports


def _extract_combat_id_from_row(row_html):
    patterns = [
        r'name=["\']combatId\[(\d+)\]["\']',
        r'combatId=(\d+)',
        r'detailedCombatId=(\d+)',
        r'combatId%3D(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, row_html, flags=re.IGNORECASE)
        if match is not None:
            return match.group(1)
    return None


def _compose_combat_message_id(combat_id, date, rounds):
    """Build a stable combat message id that changes when battle round/date changes."""
    base = "c:{}".format(combat_id)
    round_part = re.sub(r"\s+", "", str(rounds or "").strip().lower())
    date_part = re.sub(r"\s+", "", str(date or "").strip().lower())

    # If rounds/date are present, include them so ongoing battle updates are notified.
    if round_part or date_part:
        return "{}:{}:{}".format(base, round_part or "na", date_part or "na")
    return base


def _enrich_combat_details(session, messages):
    combat_messages = [m for m in messages if m.get("type") == "combat" and m.get("combat_id")]
    if not combat_messages:
        return

    player_name = str(getattr(session, "username", "")).strip().lower()

    for msg in combat_messages:
        combat_id = str(msg.get("combat_id", "")).strip()
        if not combat_id:
            continue

        urls = [
            "view=militaryReportExport&combatId={}&combatRound=0".format(combat_id),
            "view=militaryReportExport&combatId={}&combatRound=1".format(combat_id),
        ]

        detail_payloads = []
        for url in urls:
            try:
                raw = session.get(url)
            except Exception:
                raw = None
            if raw:
                detail_payloads.append(str(raw))
                detail_payloads.extend(_flatten_json_payload(raw))

        details = _parse_combat_detail_payloads(detail_payloads)
        if details is None:
            continue

        # Keep subject from combat list entry as requested.
        if details.get("date"):
            msg["date"] = details["date"]
        if details.get("town"):
            msg["town"] = details["town"]
        if details.get("sender"):
            msg["sender"] = details["sender"]
        if details.get("body"):
            msg["body"] = details["body"]
        if details.get("round"):
            msg["round"] = details["round"]

        outcome = _resolve_outcome_for_player(
            player_name,
            details.get("winner", ""),
            details.get("loser", ""),
            msg.get("outcome", ""),
        )
        if outcome:
            msg["outcome"] = outcome


def _parse_combat_detail_payloads(payloads):
    """Parse combat details only from militaryReportExport exportText content."""
    if not payloads:
        return None

    for payload in payloads:
        for candidate in _payload_variants(payload):
            export_text = _extract_export_text(candidate)
            if export_text:
                parsed = _parse_export_text_details(export_text)
                if parsed is not None:
                    return parsed

    return None


def _extract_export_text(payload):
    text = str(payload)

    # Prefer a bounded capture between exportText and exportPreview when available.
    bounded = re.search(
        r'"exportText"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"exportPreview"',
        text,
        flags=re.IGNORECASE,
    )
    match = bounded or re.search(r'"exportText"\s*:\s*"((?:[^"\\]|\\.)*)"', text, flags=re.IGNORECASE)
    if match is None:
        return ""

    escaped = match.group(1)
    try:
        return json.loads('"{}"'.format(escaped))
    except Exception:
        try:
            # Fallback decode for malformed JSON escapes.
            return bytes(escaped, "utf-8").decode("unicode_escape")
        except Exception:
            return ""


def _parse_export_text_details(export_text):
    if not export_text:
        return None

    text = str(export_text)
    low = text.lower()
    if "battle for" not in low or "vs" not in low:
        return None
    if "ajax.responder" in low or "updateglobaldata" in low:
        return None

    if "<br" in text.lower():
        text = text.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    text = html.unescape(text)

    lines = [_clean_text(line) for line in text.split("\n") if _clean_text(line)]
    if not lines:
        return None

    attacker_units, defender_units = _extract_units_from_export_lines(lines)

    subject = ""
    date = ""
    round_info = ""
    attacker = ""
    defender = ""
    winners = ""
    losers = ""
    loot = ""
    event_lines = []

    for i, line in enumerate(lines):
        if not subject and line.lower().startswith("battle for"):
            subject = line
            continue
        if not date and re.match(r"^\([^)]*\)$", line):
            candidate_date = _clean_text(line.strip("()"))
            if re.search(r"\d{1,2}\.\d{1,2}\.\d{4}", candidate_date):
                date = candidate_date
            continue
        if not round_info and line.lower().startswith("round"):
            round_info = line
            continue
        if line.lower().startswith("winners:"):
            candidate_winners = line.split(":", 1)[1].strip()
            winners = "" if _looks_like_noise_text(candidate_winners) else candidate_winners
            continue
        if line.lower().startswith("losers:"):
            candidate_losers = line.split(":", 1)[1].strip()
            losers = "" if _looks_like_noise_text(candidate_losers) else candidate_losers
            continue
        if ("has been pillaged" in line.lower() or "resources have been stolen" in line.lower()) and len(line) < 320:
            loot = _clean_text(line)
            continue
        if (
            ("miracle" in line.lower() or "withdrawn" in line.lower() or "has joined the battle" in line.lower())
            and len(line) < 240
            and not _looks_like_noise_text(line)
        ):
            if line not in event_lines:
                event_lines.append(line)
            continue

        if line.lower() == "vs" and i > 0 and i + 1 < len(lines):
            attacker = lines[i - 1]
            defender = lines[i + 1]

    if not subject and not winners and not losers and not loot:
        return None
    if subject and ("ajax.responder" in subject.lower() or "updateglobaldata" in subject.lower()):
        return None

    town = ""
    town_match = re.search(r"Battle for\s+(.+)$", subject)
    if town_match:
        town = town_match.group(1).strip()

    body_parts = []
    if attacker_units:
        body_parts.append("Attacker units: {}".format(", ".join(attacker_units[:6])))
    if defender_units:
        body_parts.append("Defender units: {}".format(", ".join(defender_units[:6])))
    if round_info:
        body_parts.append(round_info)
    if attacker or defender:
        body_parts.append("Sides: {} vs {}".format(attacker or "?", defender or "?"))
    if winners:
        body_parts.append("Winner: {}".format(winners))
    if losers:
        body_parts.append("Loser: {}".format(losers))
    if loot:
        body_parts.append("Loot: {}".format(loot))
    for event in event_lines[:2]:
        body_parts.append("Event: {}".format(event))

    # If extraction did not produce enough detail, fall back to a cleaned excerpt of export text.
    if len(body_parts) < 2:
        fallback_excerpt = _clean_export_excerpt(lines)
        if fallback_excerpt:
            body_parts = [fallback_excerpt]

    sender = winners or attacker or "Combat report"

    round_value = _extract_round_value(round_info)

    return {
        "subject": subject,
        "date": date,
        "town": town,
        "sender": sender,
        "winner": winners,
        "loser": losers,
        "round": round_value,
        "body": " | ".join(body_parts),
    }


def _resolve_outcome_for_player(player_name, winner, loser, current_outcome):
    current = str(current_outcome or "").strip()
    player = str(player_name or "").strip().lower()
    winner_low = str(winner or "").strip().lower()
    loser_low = str(loser or "").strip().lower()

    if player:
        if winner_low and player in winner_low:
            return "Win"
        if loser_low and player in loser_low:
            return "Loss"

    if current in ["Win", "Loss", "Ongoing"]:
        return current
    return "Ongoing" if current == "" else current


def _extract_round_value(round_info):
    text = str(round_info or "").strip()
    if not text:
        return ""
    m = re.search(r"(\d+)", text)
    return m.group(1) if m is not None else text


def _extract_units_from_export_lines(lines):
    attacker_units = []
    defender_units = []
    seen_attacker = set()
    seen_defender = set()

    ignore_prefixes = [
        "military",
        "offensive points",
        "defence points",
        "damage received",
        "damage percent",
        "winners:",
        "losers:",
    ]

    for line in lines:
        low = line.lower().strip()
        if not line or "(-" not in line or " - " not in line:
            continue
        if set(line.strip()) == {"-"}:
            continue
        if any(low.startswith(prefix) for prefix in ignore_prefixes):
            continue

        parts = line.split(" - ", 1)
        left = parts[0].strip()
        right = parts[1].strip() if len(parts) > 1 else ""

        left_unit = _parse_unit_side(left)
        right_unit = _parse_unit_side(right)

        if left_unit is not None and left_unit not in seen_attacker:
            attacker_units.append(left_unit)
            seen_attacker.add(left_unit)
        if right_unit is not None and right_unit not in seen_defender:
            defender_units.append(right_unit)
            seen_defender.add(right_unit)

        # Handle list format: "Doctor: 20, Cook: 25"
        if ":" in line and "," in line and "(-" not in line:
            for chunk in [part.strip() for part in line.split(",") if part.strip()]:
                colon_unit = _parse_colon_unit(chunk)
                if colon_unit is None:
                    continue
                if colon_unit not in seen_attacker:
                    attacker_units.append(colon_unit)
                    seen_attacker.add(colon_unit)

    return attacker_units, defender_units


def _parse_unit_side(side_text):
    text = side_text.strip()
    if not text:
        return None

    # Skip empty placeholders made of dots.
    if re.match(r"^\.+$", text):
        return None

    # Typical export format: UnitName.....123(-4)
    match = re.search(r"([A-Za-z][A-Za-z\s'`\-]{1,50})\.{2,}\s*(\d+\(-?\d+\))$", text)
    if match is not None:
        unit_name = match.group(1).strip()
        amount = match.group(2).strip()
        if unit_name and amount:
            return "{} {}".format(unit_name, amount)

    # Alternate matrix format: UnitName 123(-4)
    match = re.search(r"([A-Za-z][A-Za-z\s'`\-]{1,50})\s+(\d+\(-?\d+\))$", text)
    if match is not None:
        unit_name = match.group(1).strip()
        amount = match.group(2).strip()
        if unit_name and amount:
            return "{} {}".format(unit_name, amount)

    colon_unit = _parse_colon_unit(text)
    if colon_unit is not None:
        return colon_unit

    return None


def _parse_colon_unit(text):
    match = re.search(r"^([A-Za-z][A-Za-z\s'`\-]{1,50})\s*:\s*(\d+)$", text)
    if match is None:
        return None
    name = match.group(1).strip()
    amount = match.group(2).strip()
    if not name or not amount:
        return None
    return "{} {}".format(name, amount)


def _clean_export_excerpt(lines):
    if not lines:
        return ""

    cleaned = []
    ignore_prefixes = [
        "battle for",
        "military",
        "offensive points",
        "defence points",
        "damage received",
        "damage percent",
    ]

    for raw in lines:
        line = _clean_text(raw)
        if not line:
            continue
        low = line.lower()
        if set(line) == {"-"}:
            continue
        if _looks_like_noise_text(line):
            continue
        if any(low.startswith(prefix) for prefix in ignore_prefixes):
            continue
        cleaned.append(line)

    if not cleaned:
        return ""

    # Keep the first meaningful lines, preserving order from export text.
    return " | ".join(cleaned[:6])


def _looks_like_noise_text(text):
    low = str(text).strip().lower()
    if not low:
        return True

    noisy_markers = [
        "town relocation",
        "triton engines",
        "great deals",
        "ikariam",
        "ajax.responder",
        "updateglobaldata",
        "view=premium",
    ]
    return any(marker in low for marker in noisy_markers)


def _fetch_unread_count(session):
    """Best-effort unread counter detection for fallback notifications."""
    payloads = _fetch_message_payloads(session)

    patterns = [
        r'"unreadMessages?"\s*:\s*(\d+)',
        r'"newMessages?"\s*:\s*(\d+)',
        r'"unreadMessageCount"\s*:\s*(\d+)',
        r'"mailCount"\s*:\s*(\d+)',
        r'"messageCount"\s*:\s*(\d+)',
        r'data-unread\s*=\s*["\'](\d+)["\']',
        r'data-message-count\s*=\s*["\'](\d+)["\']',
        r'js_GlobalMenu_[^"\']*(?:mail|message)[^"\']*["\'][^\d]{0,40}(\d+)',
        r'tabMessages[^\d]{0,40}(\d+)',
        r'js_tabMessages[^\d]{0,40}(\d+)',
        r'tabMail[^\d]{0,40}(\d+)',
        r'js_tabMail[^\d]{0,40}(\d+)',
        r'mail[^\d]{0,20}\((\d+)\)',
    ]

    counts = []
    for payload in payloads:
        for pattern in patterns:
            for match in re.finditer(pattern, payload, flags=re.IGNORECASE):
                try:
                    counts.append(int(match.group(1)))
                except Exception:
                    continue

    if not counts:
        return None
    return max(counts)


def _estimate_message_count(session):
    """Estimate mailbox size from payload structure when explicit unread counters are unavailable."""
    payloads = _fetch_message_payloads(session)
    if not payloads:
        return None

    estimates = []
    id_pattern = re.compile(
        r'data-message-id\s*=\s*["\']?\s*(\d+)\s*["\']?|id\s*=\s*["\']\s*(?:message|msg)[_-]?(\d+)\s*["\']',
        re.IGNORECASE,
    )
    marker_patterns = [
        re.compile(r'"subject"\s*:', re.IGNORECASE),
        re.compile(r'"sender(?:Name)?"\s*:', re.IGNORECASE),
        re.compile(r'class=["\'][^"\']*subject[^"\']*["\']', re.IGNORECASE),
        re.compile(r'class=["\'][^"\']*(?:sender|from|avatarname)[^"\']*["\']', re.IGNORECASE),
    ]

    for payload in payloads:
        ids = set()
        for match in id_pattern.finditer(payload):
            ids.add(match.group(1) or match.group(2))
        if ids:
            estimates.append(len(ids))
            continue

        marker_count = sum(len(pattern.findall(payload)) for pattern in marker_patterns)
        if marker_count:
            estimates.append(max(1, marker_count // 2))

    if not estimates:
        return None
    return max(estimates)


def _fetch_message_payloads(session):
    """Collects possible message payloads from HTML pages and advisor AJAX responses."""
    payloads = []

    base_html = ""
    try:
        base_html = session.get()
        if base_html:
            payloads.append(base_html)
    except Exception:
        pass

    city_id = None
    if base_html:
        match = re.search(r"currentCityId:\s*(\d+),", base_html)
        if match:
            city_id = match.group(1)

    html_urls = [
        "view=mail",
        "view=messages",
        "view=advisor&activeTab=tabMessages",
        "view=diplomacyAdvisor",
        "view=diplomacyAdvisor&activeTab=tab_diplomacyAdvisor",
    ]
    if city_id is not None:
        html_urls.append(
            "view=advisor&activeTab=tabMessages&backgroundView=city&currentCityId={}".format(city_id)
        )
        html_urls.append(
            "view=diplomacyAdvisor&activeTab=tab_diplomacyAdvisor&backgroundView=city&currentCityId={}".format(city_id)
        )

    for url in html_urls:
        try:
            data = session.get(url)
            if data:
                payloads.append(data)
        except Exception:
            continue

    if city_id is not None:
        ajax_urls = [
            (
                "view=advisor&oldView=city&oldBackgroundView=city&backgroundView=city"
                "&currentCityId={}&templateView=advisor&actionRequest={}&activeTab=tabMessages&ajax=1"
            ).format(city_id, config.actionRequest),
            (
                "view=advisor&backgroundView=city&currentCityId={}&actionRequest={}"
                "&activeTab=tabMessages&ajax=1"
            ).format(city_id, config.actionRequest),
            (
                "view=diplomacyAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city"
                "&currentCityId={}&templateView=diplomacyAdvisor&actionRequest={}"
                "&activeTab=tab_diplomacyAdvisor&ajax=1"
            ).format(city_id, config.actionRequest),
            (
                "view=diplomacyAdvisor&backgroundView=city&currentCityId={}&actionRequest={}"
                "&activeTab=tab_diplomacyAdvisor&ajax=1"
            ).format(city_id, config.actionRequest),
        ]

        for url in ajax_urls:
            raw = None
            try:
                raw = session.post(url)
            except Exception:
                try:
                    raw = session.get(url)
                except Exception:
                    raw = None
            if raw:
                payloads.append(str(raw))
                payloads.extend(_extract_ajax_html_fragments(raw))
                payloads.extend(_flatten_json_payload(raw))

    # de-duplicate while preserving order
    unique_payloads = []
    seen = set()
    for payload in payloads:
        payload_str = str(payload)
        if not payload_str:
            continue
        if payload_str in seen:
            continue
        seen.add(payload_str)
        unique_payloads.append(payload_str)

    return unique_payloads


def _flatten_json_payload(raw):
    """Extract textual fragments from JSON-like payloads returned by ajax endpoints."""
    text = str(raw).strip()
    if not text or text[0] not in ["{", "["]:
        return []

    try:
        parsed = json.loads(text)
    except Exception:
        return []

    fragments = []

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
            return
        if isinstance(node, list):
            for value in node:
                walk(value)
            return
        if isinstance(node, str):
            value = node.strip()
            if value:
                fragments.append(value)

    walk(parsed)
    return fragments


def _extract_ajax_html_fragments(raw):
    """Extract HTML fragments from Ikariam-style AJAX command arrays.

    In many views, response is a list of commands like:
    ["changeView", [templateName, "<html...>"]]
    We extract those HTML strings explicitly instead of hoping regex catches them in raw text.
    """
    text = str(raw).strip()
    if not text or text[0] not in ["[", "{"]:
        return []

    try:
        parsed = json.loads(text, strict=False)
    except Exception:
        return []

    fragments = []

    def maybe_add_html(value):
        if not isinstance(value, str):
            return
        candidate = value.strip()
        if not candidate:
            return
        low = candidate.lower()
        if "<tr" in low or "<table" in low or "id=\"message" in low or "id='message" in low:
            fragments.append(candidate)

    def walk(node):
        if isinstance(node, list):
            if node:
                command = node[0] if isinstance(node[0], str) else ""
                if isinstance(command, str):
                    cmd_low = command.lower()
                    if cmd_low in ["changeview", "updatetemplatedata", "sethtml", "replacehtml"]:
                        for part in node[1:]:
                            walk(part)
                        return
            for item in node:
                walk(item)
            return

        if isinstance(node, dict):
            for value in node.values():
                walk(value)
            return

        maybe_add_html(node)

    walk(parsed)

    # De-duplicate while preserving order.
    unique = []
    seen = set()
    for fragment in fragments:
        if fragment in seen:
            continue
        seen.add(fragment)
        unique.append(fragment)
    return unique


def _payload_variants(payload):
    """Generate normalized variants for payloads that may be escaped JSON/HTML."""
    text = str(payload)
    if not text:
        return []

    candidates = [text]

    def decode_unicode_escapes(value):
        return re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda m: chr(int(m.group(1), 16)),
            value,
        )

    # Try decoding JSON string wrappers and escaped unicode HTML markers.
    base_for_decode = [text, html.unescape(text)]
    for value in base_for_decode:
        candidates.append(value)
        candidates.append(value.replace(r"\/", "/"))
        candidates.append(decode_unicode_escapes(value))
        candidates.append(decode_unicode_escapes(value).replace(r"\/", "/"))

        stripped = value.strip()
        if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
            try:
                decoded = json.loads(stripped)
                if isinstance(decoded, str) and decoded:
                    candidates.append(decoded)
                    candidates.append(html.unescape(decoded))
                    candidates.append(decode_unicode_escapes(decoded))
            except Exception:
                pass

    # Deduplicate while preserving order.
    variants = []
    seen = set()
    for value in candidates:
        candidate = str(value)
        if not candidate:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        variants.append(candidate)

    return variants


def _parse_messages_from_payload(payload):
    results = {}

    # Pattern 0: explicit mailbox table rows (matches real Ikariam inbox DOM)
    for message in _parse_messages_from_table_rows(payload):
        results[message["id"]] = message

    # Pattern 1: ids appearing in data attributes or element ids
    id_matches = list(
        re.finditer(
            r'data-message-id\s*=\s*["\']?\s*(\d+)\s*["\']?|id\s*=\s*["\']\s*(?:message|msg)[_-]?(\d+)\s*["\']',
            payload,
            flags=re.IGNORECASE,
        )
    )

    for match in id_matches:
        msg_id = match.group(1) or match.group(2)
        if not msg_id:
            continue

        start = max(0, match.start() - 400)
        end = min(len(payload), match.end() + 800)
        snippet = payload[start:end]

        if not _is_probable_message_snippet(snippet):
            continue

        message_type = _detect_type(snippet)
        sender = _extract_sender(snippet)
        subject = _extract_subject(snippet)
        recovered = _recover_message_fields_by_id(payload, msg_id)
        if recovered is not None:
            sender = recovered.get("sender", sender)
            subject = recovered.get("subject", subject)

        canonical_id = _canonical_message_id(msg_id)
        message = {
            "id": canonical_id,
            "type": message_type,
            "sender": sender,
            "subject": subject,
            "body": recovered.get("body", "") if recovered is not None else "",
            "town": recovered.get("town", "") if recovered is not None else "",
            "date": recovered.get("date", "") if recovered is not None else "",
        }
        message = _normalize_message(message)
        if _is_low_quality_message(message):
            continue

        results[canonical_id] = message

    # Pattern 3: message-like JSON/HTML blocks with sender+subject but without explicit numeric IDs
    for snippet in _extract_message_like_blocks(payload):
        message = {
            "id": _make_message_id(snippet),
            "type": _detect_type(snippet),
            "sender": _extract_sender(snippet),
            "subject": _extract_subject(snippet),
        }
        message = _normalize_message(message)
        if _is_low_quality_message(message):
            continue
        if message["id"] in results:
            continue
        results[message["id"]] = message

    # Pattern 2: JSON-like message blocks where id/type/sender/subject are serialized
    for match in re.finditer(r'"id"\s*:\s*"?(\d+)"?', payload):
        msg_id = match.group(1)
        if msg_id in results:
            continue

        start = max(0, match.start() - 300)
        end = min(len(payload), match.end() + 700)
        snippet = payload[start:end]

        if not _is_probable_message_snippet(snippet):
            continue

        canonical_id = _canonical_message_id(msg_id)
        message = {
            "id": canonical_id,
            "type": _detect_type(snippet),
            "sender": _extract_sender(snippet),
            "subject": _extract_subject(snippet),
        }
        recovered = _recover_message_fields_by_id(payload, msg_id)
        if recovered is not None:
            message["sender"] = recovered.get("sender", message["sender"])
            message["subject"] = recovered.get("subject", message["subject"])
            message["body"] = recovered.get("body", "")
            message["town"] = recovered.get("town", "")
            message["date"] = recovered.get("date", "")
        message = _normalize_message(message)
        if _is_low_quality_message(message):
            continue

        results[canonical_id] = message

    return list(results.values())


def _parse_messages_from_table_rows(payload):
    messages = {}
    body_by_suffix = _parse_message_bodies_by_suffix(payload)

    row_pattern = re.compile(
        r'<tr[^>]*id\s*=\s*["\']\s*(g?message\d+)\s*["\'][^>]*>([\s\S]*?)</tr>',
        flags=re.IGNORECASE,
    )

    for row_match in row_pattern.finditer(payload):
        row_id = row_match.group(1).strip()
        row_html = row_match.group(2)

        sender = _extract_sender_from_row(row_html)
        subject = _extract_subject_from_row(row_html)
        town, date = _extract_town_and_date_from_row(row_html)
        suffix = _extract_row_suffix(row_id)
        body = body_by_suffix.get(suffix, "") if suffix is not None else ""
        canonical_id = _canonical_message_id(row_id)

        message = {
            "id": canonical_id,
            "type": "system" if row_id.lower().startswith("gmessage") or sender.lower() == "ikariam" else "player",
            "sender": sender,
            "subject": subject,
            "body": body,
            "town": town,
            "date": date,
        }
        message = _normalize_message(message)
        if _is_low_quality_message(message):
            continue

        messages[message["id"]] = message

    return list(messages.values())


def _recover_message_fields_by_id(payload, msg_id):
    """Recover sender/subject/body using deterministic row+body ids for a known message id."""
    suffix = str(msg_id).strip()
    if not suffix.isdigit():
        return None

    row_match = re.search(
        r'<tr[^>]*id\s*=\s*["\']\s*(?:gmessage|message){}\s*["\'][^>]*>([\s\S]*?)</tr>'.format(
            re.escape(suffix)
        ),
        payload,
        flags=re.IGNORECASE,
    )
    if row_match is None:
        return None

    row_html = row_match.group(1)
    sender = _extract_sender_from_row(row_html)
    subject = _extract_subject_from_row(row_html)
    town, date = _extract_town_and_date_from_row(row_html)

    body_match = re.search(
        r'<tr[^>]*id\s*=\s*["\']\s*tbl_(?:g?mail){}\s*["\'][^>]*>[\s\S]*?'
        r'<td[^>]*class=["\'][^"\']*msgText[^"\']*["\'][^>]*>([\s\S]*?)</td>[\s\S]*?</tr>'.format(
            re.escape(suffix)
        ),
        payload,
        flags=re.IGNORECASE,
    )
    body = _clean_text(body_match.group(1)) if body_match is not None else ""

    return {"sender": sender, "subject": subject, "body": body, "town": town, "date": date}


def _extract_town_and_date_from_row(row_html):
    tds = re.findall(r'<td[^>]*>([\s\S]*?)</td>', row_html, flags=re.IGNORECASE)
    if len(tds) >= 6:
        town = _clean_text(tds[4])
        date = _clean_text(tds[5])
        return town, date
    return "", ""


def _canonical_message_id(raw_id):
    value = str(raw_id).strip().lower()
    if not value:
        return ""

    m = re.match(r"^gmessage(\d+)$", value)
    if m:
        return "g:{}".format(m.group(1))

    m = re.match(r"^message(\d+)$", value)
    if m:
        return "m:{}".format(m.group(1))

    if value.isdigit():
        return "m:{}".format(value)

    return value


def _extract_sender_from_row(row_html):
    avatar = re.search(
        r'<span[^>]*class=["\'][^"\']*avatarName[^"\']*["\'][^>]*>([\s\S]*?)</span>',
        row_html,
        flags=re.IGNORECASE,
    )
    if avatar:
        sender = _clean_text(avatar.group(1))
        if sender:
            return sender

    tds = re.findall(r'<td[^>]*>([\s\S]*?)</td>', row_html, flags=re.IGNORECASE)
    if len(tds) >= 3:
        sender = _clean_text(tds[2])
        if sender:
            return sender

    return "Unknown sender"


def _extract_subject_from_row(row_html):
    subject_match = re.search(
        r'<td[^>]*class=["\'][^"\']*subject[^"\']*["\'][^>]*>([\s\S]*?)</td>',
        row_html,
        flags=re.IGNORECASE,
    )
    if subject_match:
        subject = _clean_text(subject_match.group(1))
        if subject:
            return subject

    tds = re.findall(r'<td[^>]*>([\s\S]*?)</td>', row_html, flags=re.IGNORECASE)
    if len(tds) >= 4:
        subject = _clean_text(tds[3])
        if subject:
            return subject

    return "No subject"


def _clean_text(value):
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_row_suffix(row_id):
    match = re.search(r"(\d+)$", row_id)
    if match is None:
        return None
    return match.group(1)


def _parse_message_bodies_by_suffix(payload):
    bodies = {}
    body_pattern = re.compile(
        r'<tr[^>]*id\s*=\s*["\']\s*tbl_(?:g?mail)(\d+)\s*["\'][^>]*>[\s\S]*?'
        r'<td[^>]*class=["\'][^"\']*msgText[^"\']*["\'][^>]*>([\s\S]*?)</td>[\s\S]*?</tr>',
        flags=re.IGNORECASE,
    )

    for match in body_pattern.finditer(payload):
        suffix = match.group(1)
        body = _clean_text(match.group(2))
        bodies[suffix] = body

    return bodies


def _detect_type(text):
    low = text.lower()
    if any(k in low for k in ["spy", "espionage", "spy report", "espionagereport", "spyreport"]):
        return "spy"
    if any(k in low for k in ["combat", "battle", "military report", "fight report", "combatreport", "battle report"]):
        return "combat"
    if any(k in low for k in ["system", "administrator", "admin", "notification"]):
        return "system"
    if any(k in low for k in ["message", "mail", "inbox", "sender", "from"]):
        return "player"
    return "unknown"


def _extract_sender(text):
    patterns = [
        r'"sender(?:Name)?"\s*:\s*"([^"\\]{1,80})"',
        r'"from"\s*:\s*"([^"\\]{1,80})"',
        r'<[^>]*class=["\'][^"\']*(?:sender|from|avatarname)[^"\']*["\'][^>]*>([^<]{1,80})<',
        r'from\s*:\s*([^<\n\r]{1,80})',
        r'from\s*</[^>]+>\s*<[^>]*>\s*([^<]{1,80})\s*<',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "Unknown sender"


def _extract_subject(text):
    patterns = [
        r'"subject"\s*:\s*"([^"\\]{1,120})"',
        r'"title"\s*:\s*"([^"\\]{1,120})"',
        r'<[^>]*class=["\'][^"\']*subject[^"\']*["\'][^>]*>([^<]{1,120})<',
        r'<a[^>]*class=["\'][^"\']*(?:subject|messageTitle|title)[^"\']*["\'][^>]*>([^<]{1,120})<',
        r'subject\s*:\s*([^<\n\r]{1,120})',
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "No subject"


def _parse_type_selection(raw_selection):
    mapping = {
        "1": {"player", "combat"},
        "2": {"player"},
        "3": {"combat"},
    }

    selected = set()
    for token in [part.strip() for part in raw_selection.split(",") if part.strip()]:
        selected.update(mapping.get(token, set()))

    if not selected:
        selected = mapping["1"].copy()

    return selected


def _filter_messages(messages, enabled_types):
    return [
        m
        for m in messages
        if m.get("type", "unknown") in enabled_types and not _is_low_quality_message(m)
    ]


def _notify_messages(session, messages):
    if not messages:
        return

    report_blocks = []
    for msg in messages:
        lines = []
        lines.append("- [{}] {}".format(
            TYPE_LABELS.get(msg.get("type", "unknown"), "Unknown"), msg.get("sender", "Unknown sender")
        ))
        lines.append("  Subject: {}".format(msg.get("subject", "No subject")))
        if msg.get("type") == "combat":
            outcome = str(msg.get("outcome", "")).strip()
            if not outcome:
                outcome = _extract_outcome_from_body(str(msg.get("body", "")))
            if outcome:
                lines.append("  Outcome: {}".format(outcome))
            round_value = str(msg.get("round", "")).strip()
            if not round_value:
                round_value = _extract_round_from_body(str(msg.get("body", "")))
            if round_value:
                lines.append("  Round: {}".format(round_value))
        town = str(msg.get("town", "")).strip()
        date = str(msg.get("date", "")).strip()
        if town or date:
            if town and date:
                lines.append("  Town/Time: {} | {}".format(town, date))
            elif town:
                lines.append("  Town: {}".format(town))
            else:
                lines.append("  Time: {}".format(date))
        body = str(msg.get("body", "")).strip()
        if body:
            if msg.get("type") == "combat":
                lines.append("  Details:")
                parts = [part.strip() for part in body.split(" | ") if part.strip()]
                if parts:
                    for part in parts:
                        lines.append("    - {}".format(part))
                else:
                    lines.append("    {}".format(body))
            else:
                lines.append("  Text:")
                for chunk in [line.strip() for line in body.split("\n") if line.strip()]:
                    lines.append("    {}".format(chunk))
        report_blocks.append("\n".join(lines))

    _send_report_blocks_chunked(session, "-- NEW IN-GAME MESSAGES --", report_blocks)


def _extract_outcome_from_body(body):
    text = str(body)
    match = re.search(r"(?:^|\b)Outcome:\s*([^,|\n]+)", text, flags=re.IGNORECASE)
    if match is not None:
        return match.group(1).strip()

    low = text.lower()
    if "winner:" in low or "winners:" in low:
        return "Resolved"
    return ""


def _extract_round_from_body(body):
    text = str(body)
    m = re.search(r"(?:^|\b)Rounds?:\s*(\d+)", text, flags=re.IGNORECASE)
    if m is not None:
        return m.group(1).strip()

    m = re.search(r"(?:^|\b)Round\s+(\d+)", text, flags=re.IGNORECASE)
    if m is not None:
        return m.group(1).strip()
    return ""


def _notify_unparsed_count(session, delta):
    if delta <= 0:
        return
    _send_to_bot_chunked(
        session,
        "-- NEW IN-GAME MESSAGES --\n"
        + "Detected {} new message(s), but detailed sender/subject parsing is unavailable on this server format.".format(delta),
    )


def _notify_movement_report(session):
    try:
        movements, time_now = _fetch_military_movements(session)
    except Exception:
        msg = "Error while fetching movement report:\n{}".format(traceback.format_exc())
        _send_to_bot_chunked(session, msg)
        return

    if movements is None:
        return

    if len(movements) == 0:
        return

    report_blocks = []
    for movement in movements:
        report_blocks.append(_format_movement_report_block(movement, time_now))

    _send_report_blocks_chunked(session, "-- MOVEMENT REPORT --", report_blocks)


def _fetch_military_movements(session):
    html_home = session.get()
    city_id_match = re.search(r"currentCityId:\s*(\d+),", html_home)
    if city_id_match is None:
        return None, int(time.time())

    city_id = city_id_match.group(1)
    url = (
        "view=militaryAdvisor&oldView=city&oldBackgroundView=city&backgroundView=city"
        "&currentCityId={}&actionRequest={}&ajax=1"
    ).format(city_id, config.actionRequest)
    response = session.post(url)
    postdata = json.loads(response, strict=False)
    movements = postdata[1][1][2]["viewScriptParams"]["militaryAndFleetMovements"]
    time_now = int(postdata[0][1].get("time", int(time.time())))
    return movements, time_now


def _format_movement_report_block(movement, time_now):
    origin = "{} ({})".format(movement["origin"]["name"], movement["origin"]["avatarName"])
    destination = "{} ({})".format(movement["target"]["name"], movement["target"]["avatarName"])
    arrow = "<-" if movement["event"].get("isFleetReturning") else "->"
    time_left = int(movement["eventTime"]) - int(time_now)
    lines = [
        "- {} {} {}".format(origin, arrow, destination),
        "  Mission: {}".format(movement["event"].get("missionText", "Unknown")),
        "  Arrival in: {}".format(daysHoursMinutes(max(0, time_left))),
        "  Relation: {}".format(_movement_relation_label(movement)),
    ]

    army_amount = int(movement.get("army", {}).get("amount", 0) or 0)
    fleet_amount = int(movement.get("fleet", {}).get("amount", 0) or 0)
    transport_ships = 0
    war_ships = 0
    for ship in movement.get("fleet", {}).get("ships", []):
        amount = int(ship.get("amount", 0) or 0)
        if ship.get("cssClass") == "ship_transport":
            transport_ships += amount
        else:
            war_ships += amount

    if army_amount:
        lines.append("  Troops: {}".format(addThousandSeparator(army_amount)))
    if fleet_amount:
        lines.append("  Fleets: {}".format(addThousandSeparator(fleet_amount)))
    if transport_ships:
        lines.append("  Transport ships: {}".format(addThousandSeparator(transport_ships)))
    if war_ships:
        lines.append("  War ships: {}".format(addThousandSeparator(war_ships)))

    resource_lines = []
    for resource in movement.get("resources", []):
        amount = resource.get("amount", "0")
        css_class = resource.get("cssClass", "")
        resource_name = css_class.split()[-1] if css_class else "resource"
        resource_lines.append("{} {}".format(amount, resource_name))
    if resource_lines:
        lines.append("  Cargo: {}".format(", ".join(resource_lines)))

    return "\n".join(lines)


def _movement_relation_label(movement):
    if movement.get("isHostile"):
        return "Hostile"
    if movement.get("isOwnArmyOrFleet"):
        return "Own"
    if movement.get("isSameAlliance"):
        return "Alliance"
    return "Neutral"


def _send_to_bot_chunked(session, text, max_len=3500):
    payload = str(text)
    if len(payload) <= max_len:
        sendToBot(session, payload)
        return

    chunks = []
    current = []
    current_len = 0

    for line in payload.split("\n"):
        line_len = len(line) + 1

        # Handle pathological single lines by slicing them safely.
        if line_len > max_len:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            start = 0
            while start < len(line):
                end = min(start + max_len - 1, len(line))
                chunks.append(line[start:end])
                start = end
            continue

        if current_len + line_len > max_len and current:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunks.append("\n".join(current))

    for index, chunk in enumerate(chunks):
        if len(chunks) == 1:
            sendToBot(session, chunk)
        else:
            sendToBot(session, "[Part {}/{}]\n{}".format(index + 1, len(chunks), chunk))


def _send_report_blocks_chunked(session, header, report_blocks, max_len=3300):
    if not report_blocks:
        _send_to_bot_chunked(session, header, max_len=max_len)
        return

    chunks = []
    current = header

    def add_chunk(text):
        if text and text.strip():
            chunks.append(text)

    for report in report_blocks:
        candidate = "{}\n\n{}".format(current, report)
        if len(candidate) <= max_len:
            current = candidate
            continue

        # Flush current chunk and start a new chunk with this report.
        add_chunk(current)
        next_chunk = "{}\n\n{}".format(header, report)
        if len(next_chunk) <= max_len:
            current = next_chunk
            continue

        # Single report is too large: split by lines, but never mix with next report.
        for split_report in _split_large_report_block(report, max_len - len(header) - 2):
            add_chunk("{}\n\n{}".format(header, split_report))
        current = header

    add_chunk(current)

    for index, chunk in enumerate(chunks):
        if len(chunks) == 1:
            sendToBot(session, chunk)
        else:
            sendToBot(session, "[Part {}/{}]\n{}".format(index + 1, len(chunks), chunk))


def _split_large_report_block(report, max_len):
    parts = []
    current_lines = []
    current_len = 0

    for line in report.split("\n"):
        line_len = len(line) + 1
        if line_len > max_len:
            if current_lines:
                parts.append("\n".join(current_lines))
                current_lines = []
                current_len = 0
            start = 0
            while start < len(line):
                end = min(start + max_len - 1, len(line))
                parts.append(line[start:end])
                start = end
            continue

        if current_len + line_len > max_len and current_lines:
            parts.append("\n".join(current_lines))
            current_lines = [line]
            current_len = line_len
        else:
            current_lines.append(line)
            current_len += line_len

    if current_lines:
        parts.append("\n".join(current_lines))

    return parts


def _format_enabled_types(enabled_types):
    ordered = ["player", "combat"]
    labels = [TYPE_LABELS[t] for t in ordered if t in enabled_types]
    return ", ".join(labels)


def _is_probable_message_snippet(snippet):
    low = snippet.lower()
    positive_markers = [
        "message",
        "mail",
        "inbox",
        "sender",
        "subject",
        "from",
        "msg",
    ]
    return any(marker in low for marker in positive_markers)


def _is_low_quality_message(message):
    sender = str(message.get("sender", "")).strip().lower()
    subject = str(message.get("subject", "")).strip().lower()
    mtype = str(message.get("type", "unknown")).strip().lower()
    body = str(message.get("body", "")).strip().lower()

    # Keep messages that at least carry body text, even if sender/subject extraction failed.
    if sender in ["", "unknown sender"] and subject in ["", "no subject"] and body == "":
        return True
    return False


def _normalize_message(message):
    sender = str(message.get("sender", "")).strip().lower()
    subject = str(message.get("subject", "")).strip().lower()
    mtype = str(message.get("type", "unknown")).strip().lower()
    body = str(message.get("body", "")).strip().lower()

    # If we extracted useful fields but type detection failed, classify as player message.
    if mtype == "unknown" and (
        sender not in ["", "unknown sender"]
        or subject not in ["", "no subject"]
        or body != ""
    ):
        message["type"] = "player"

    return message


def _extract_message_like_blocks(payload):
    blocks = []

    # JSON-like object containing both sender/from and subject/title keys
    json_like_patterns = [
        r'\{[^{}]{0,2000}(?:"sender"|"senderName"|"from")[^{}]{0,1200}(?:"subject"|"title")[^{}]{0,2000}\}',
        r'\{[^{}]{0,2000}(?:"subject"|"title")[^{}]{0,1200}(?:"sender"|"senderName"|"from")[^{}]{0,2000}\}',
    ]

    for pattern in json_like_patterns:
        for match in re.finditer(pattern, payload, flags=re.IGNORECASE):
            blocks.append(match.group(0))

    # HTML-like rows containing sender/from and subject/title markers
    html_like_patterns = [
        r'<tr[^>]*>[^<]{0,1000}(?:sender|from|avatarname)[\s\S]{0,3000}(?:subject|title|messagetitle)[\s\S]{0,3000}</tr>',
        r'<li[^>]*>[^<]{0,1000}(?:sender|from|avatarname)[\s\S]{0,3000}(?:subject|title|messagetitle)[\s\S]{0,3000}</li>',
        r'<div[^>]*>[^<]{0,1000}(?:sender|from|avatarname)[\s\S]{0,3000}(?:subject|title|messagetitle)[\s\S]{0,3000}</div>',
    ]

    for pattern in html_like_patterns:
        for match in re.finditer(pattern, payload, flags=re.IGNORECASE):
            blocks.append(match.group(0))

    # Deduplicate while preserving order
    unique_blocks = []
    seen = set()
    for block in blocks:
        normalized = block.strip()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_blocks.append(normalized)

    return unique_blocks


def _make_message_id(snippet):
    digest = hashlib.md5(snippet.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return "m-{}".format(digest)

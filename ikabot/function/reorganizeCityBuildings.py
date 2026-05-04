#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import time
from collections import defaultdict

from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *


# palace and palaceColony occupy the same logical role — treat as equivalent
_GOVERNMENT_BUILDINGS = {'palace', 'palaceColony'}


def _normalize(building):
    return 'government' if building in _GOVERNMENT_BUILDINGS else building


def _compute_moves(template_city, target_city):
    """
    Returns a list of (from_pos, to_pos) swaps that transform the target
    city's building layout to match the template city's layout.
    Buildings that exist in the template but not in the target are skipped.
    """
    # Group template positions by normalized building type (sorted)
    template_by_type = defaultdict(list)
    for slot in template_city['position']:
        if slot['building'] != 'empty':
            template_by_type[_normalize(slot['building'])].append(slot['position'])
    for k in template_by_type:
        template_by_type[k].sort()

    # Group target positions by normalized building type (sorted)
    target_by_type = defaultdict(list)
    for slot in target_city['position']:
        if slot['building'] != 'empty':
            target_by_type[_normalize(slot['building'])].append(slot['position'])
    for k in target_by_type:
        target_by_type[k].sort()

    # Build assignment: desired_pos → original_pos
    # "the building originally at original_pos should end up at desired_pos"
    assignment = {}
    for btype, template_positions in template_by_type.items():
        available = target_by_type.get(btype, [])
        for i, desired_pos in enumerate(template_positions):
            if i >= len(available):
                break
            original_pos = available[i]
            if original_pos != desired_pos:
                assignment[desired_pos] = original_pos

    if not assignment:
        return []

    # Track current position of each building being relocated
    # key: original_pos, value: current_pos (changes as swaps are applied)
    tracker = {orig: orig for orig in assignment.values()}
    reverse_tracker = {v: k for k, v in tracker.items()}

    moves = []
    for desired_pos, original_pos in assignment.items():
        current = tracker[original_pos]
        if current == desired_pos:
            continue

        moves.append((current, desired_pos))

        # Update tracker to reflect the swap
        displaced_original = reverse_tracker.get(desired_pos)
        tracker[original_pos] = desired_pos
        reverse_tracker[desired_pos] = original_pos
        if desired_pos in reverse_tracker:
            reverse_tracker.pop(current, None)
        if displaced_original is not None:
            tracker[displaced_original] = current
            reverse_tracker[current] = displaced_original

    return moves


def reorganizeCityBuildings(session, event, stdin_fd, predetermined_input):
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
        print('Select the template city (the layout to copy from):')
        template_city = chooseCity(session)

        banner()
        print('Select the cities to reorganize:')
        target_city_ids, _ = ignoreCities(session, msg='Select target cities:')

        for city_id in target_city_ids:
            if str(city_id) == str(template_city['id']):
                continue

            html = session.get(city_url + city_id)
            target_city = getCity(html)

            moves = _compute_moves(template_city, target_city)

            if not moves:
                print('{}: layout already matches template, no changes needed.'.format(
                    target_city['cityName']))
                continue

            # Open the reorganization dialog (mimics clicking the button in-game)
            dialog_params = (
                'view=saveCityBuildingsPositions'
                '&cityId={city_id}'
                '&backgroundView=city'
                '&currentCityId={city_id}'
                '&actionRequest={actionRequest}'
                '&ajax=1'
            ).format(city_id=city_id, actionRequest=actionRequest)
            session.post(dialog_params, noIndex=True)

            # Simulate time spent looking at the layout before dragging
            time.sleep(random.uniform(2.0, 5.0))

            # Simulate drag-and-drop: ~1–3 s per move
            time.sleep(random.uniform(1.0, 3.0) * len(moves))

            params = {
                'action': 'SaveBuildingPositions',
                'backgroundView': 'city',
                'currentCityId': city_id,
                'templateView': 'saveCityBuildingsPositions',
                'actionRequest': actionRequest,
                'ajax': '1',
                'cityId': city_id,
            }
            for i, (from_pos, to_pos) in enumerate(moves):
                params['moves[{}][from]'.format(i)] = from_pos
                params['moves[{}][to]'.format(i)] = to_pos

            session.post(params=params, noIndex=True)
            print('{}: reorganized with {} move(s).'.format(
                target_city['cityName'], len(moves)))

            # Pause between cities to avoid looking like a bot
            time.sleep(random.uniform(3.0, 7.0))

        enter()
        event.set()
    except KeyboardInterrupt:
        event.set()

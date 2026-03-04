#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
import traceback

from ikabot import config
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import *
from ikabot.helpers.market import *
from ikabot.helpers.pedirInfo import read
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import addThousandSeparator, wait, getDateTime
from ikabot.function.sellResources import getMarketInfo, chooseCommercialCity


# Trade type constants
TRADE_BUY = "333"
TRADE_SELL = "444"
MAX_BUY_AMOUNT = 40000000

# Parameter name mapping: index -> (amount_key, price_key, type_key)
RESOURCE_PARAMS = [
    ("resource", "resourcePrice", "resourceTradeType"),
    ("tradegood1", "tradegood1Price", "tradegood1TradeType"),
    ("tradegood2", "tradegood2Price", "tradegood2TradeType"),
    ("tradegood3", "tradegood3Price", "tradegood3TradeType"),
    ("tradegood4", "tradegood4Price", "tradegood4TradeType"),
]


def buildUpdatePayload(city, trade_config, amounts):
    """Builds the POST payload for updateOffers.
    Parameters
    ----------
    city : dict
    trade_config : list[dict]
    amounts : list[int]
        The amount to set for each resource in this cycle
    Returns
    -------
    payload : dict
    """
    payload = {
        "cityId": city["id"],
        "position": city["pos"],
        "action": "CityScreen",
        "function": "updateOffers",
        "backgroundView": "city",
        "currentCityId": city["id"],
        "templateView": "branchOfficeOwnOffers",
        "currentTab": "tab_branchOfficeOwnOffers",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    for i, (amt_key, price_key, type_key) in enumerate(RESOURCE_PARAMS):
        cfg = trade_config[i]
        payload[type_key] = cfg["type"] if cfg["type"] else TRADE_SELL
        payload[amt_key] = str(amounts[i])
        payload[price_key] = str(cfg["price"]) if cfg["price"] else "1"
    return payload


def run_auto_trader(session, city, trade_config, interval_minutes):
    """Background loop that manages marketplace offers.
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trade_config : list[dict]
        List of 5 dicts with keys: type, amount, price, total, traded_so_far
    interval_minutes : int
    """
    # Post initial offers
    html = getMarketInfo(session, city)
    current_amounts = onSellInMarket(html)
    storage_cap = storageCapacityOfMarket(html)

    # Calculate and post initial amounts
    amounts = _calculate_amounts(trade_config, current_amounts, storage_cap, session, city)
    payload = buildUpdatePayload(city, trade_config, amounts)
    session.post(params=payload)
    last_posted = amounts[:]

    _update_status(session, city, trade_config, "Started")

    while True:
        wait(interval_minutes * 60, maxrandom=60)

        html = getMarketInfo(session, city)
        current_amounts = onSellInMarket(html)
        storage_cap = storageCapacityOfMarket(html)

        # Detect fulfilled trades
        notifications = []
        for i, cfg in enumerate(trade_config):
            if not cfg["type"]:
                continue
            diff = max(0, last_posted[i] - current_amounts[i])
            if diff > 0:
                cfg["traded_so_far"] += diff
                if cfg["type"] == TRADE_SELL:
                    gold_earned = diff * cfg["price"]
                    notifications.append(
                        "Sold {} {} @ {} = {} gold".format(
                            addThousandSeparator(diff),
                            materials_names[i],
                            cfg["price"],
                            addThousandSeparator(gold_earned),
                        )
                    )
                else:
                    gold_spent = diff * cfg["price"]
                    notifications.append(
                        "Bought {} {} @ {} = {} gold spent".format(
                            addThousandSeparator(diff),
                            materials_names[i],
                            cfg["price"],
                            addThousandSeparator(gold_spent),
                        )
                    )

        # Send notifications if any trades happened
        if notifications:
            msg = "Auto Trader [{}]:\n".format(city["name"])
            msg += "\n".join("  " + n for n in notifications)
            for i, cfg in enumerate(trade_config):
                if cfg["type"] and cfg["total"] is not None:
                    msg += "\n  {}: {}/{} done".format(
                        materials_names[i],
                        addThousandSeparator(cfg["traded_so_far"]),
                        addThousandSeparator(cfg["total"]),
                    )
            sendToBot(session, msg)

        # Check if all fixed-total resources are complete
        all_done = True
        for cfg in trade_config:
            if not cfg["type"]:
                continue
            if cfg["total"] is None:
                all_done = False
                break
            if cfg["traded_so_far"] < cfg["total"]:
                all_done = False
                break
        if all_done and any(c["type"] for c in trade_config):
            msg = "Auto Trader [{}]: All targets reached!\n".format(city["name"])
            for i, cfg in enumerate(trade_config):
                if cfg["type"]:
                    action = "Bought" if cfg["type"] == TRADE_BUY else "Sold"
                    msg += "  {} {} {} @ {}\n".format(
                        action,
                        addThousandSeparator(cfg["traded_so_far"]),
                        materials_names[i],
                        cfg["price"],
                    )
            sendToBot(session, msg)
            return

        # Recalculate and refill offers
        amounts = _calculate_amounts(trade_config, current_amounts, storage_cap, session, city)
        payload = buildUpdatePayload(city, trade_config, amounts)
        session.post(params=payload)
        last_posted = amounts[:]

        _update_status(session, city, trade_config, getDateTime())


def _calculate_amounts(trade_config, current_amounts, storage_cap, session, city):
    """Calculate the amounts to post for each resource.
    Parameters
    ----------
    trade_config : list[dict]
    current_amounts : list[int]
    storage_cap : int
    session : ikabot.web.session.Session
    city : dict
    Returns
    -------
    amounts : list[int]
    """
    amounts = [0] * 5

    # First pass: calculate sell amounts (they share storage)
    total_sell = 0
    for i, cfg in enumerate(trade_config):
        if cfg["type"] == TRADE_SELL:
            desired = cfg["amount"]
            if cfg["total"] is not None:
                remaining = max(0, cfg["total"] - cfg["traded_so_far"])
                desired = min(desired, remaining)
            amounts[i] = desired
            total_sell += desired

    # Enforce storage capacity for sell orders
    if total_sell > storage_cap:
        ratio = storage_cap / total_sell if total_sell > 0 else 0
        for i, cfg in enumerate(trade_config):
            if cfg["type"] == TRADE_SELL:
                amounts[i] = int(amounts[i] * ratio)

    # Second pass: calculate buy amounts (they use gold)
    gold, _ = getGold(session, city)
    for i, cfg in enumerate(trade_config):
        if cfg["type"] == TRADE_BUY:
            desired = cfg["amount"]
            if cfg["total"] is not None:
                remaining = max(0, cfg["total"] - cfg["traded_so_far"])
                desired = min(desired, remaining)
            desired = min(desired, MAX_BUY_AMOUNT)
            # Limit by gold
            if cfg["price"] > 0:
                affordable = gold // cfg["price"]
                desired = min(desired, affordable)
                gold -= desired * cfg["price"]
            amounts[i] = desired

    return amounts


def _update_status(session, city, trade_config, timestamp):
    """Update the process status line."""
    parts = []
    for i, cfg in enumerate(trade_config):
        if not cfg["type"]:
            continue
        action = "BUY" if cfg["type"] == TRADE_BUY else "SELL"
        name = materials_names[i][:3]
        if cfg["total"] is not None:
            parts.append("{} {}:{}/{}".format(
                action, name,
                addThousandSeparator(cfg["traded_so_far"]),
                addThousandSeparator(cfg["total"]),
            ))
        else:
            parts.append("{} {}:{}@{}".format(action, name, addThousandSeparator(cfg["amount"]), cfg["price"]))
    status = "AutoTrader [{}] {} | {}".format(city["name"], " ".join(parts), timestamp)
    session.setStatus(status)


def autoMarketTrader(session, event, stdin_fd, predetermined_input):
    """Entry point for the auto market trader.
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

        commercial_cities = getCommercialCities(session)
        if len(commercial_cities) == 0:
            print("No city has a Trading Post built.")
            enter()
            event.set()
            return

        if len(commercial_cities) == 1:
            city = commercial_cities[0]
        else:
            city = chooseCommercialCity(commercial_cities)
            banner()

        # Fetch marketplace state
        html = getMarketInfo(session, city)
        storage_cap = storageCapacityOfMarket(html)
        current_amounts = onSellInMarket(html)
        price_limits = getPriceLimits(html)
        current_prices = getOwnOfferPrices(html)
        current_types = getOwnOfferTradeTypes(html)
        gold, _ = getGold(session, city)

        print("City: {}".format(city["name"]))
        print("Storage capacity: {}".format(addThousandSeparator(storage_cap)))
        print("Gold: {}\n".format(addThousandSeparator(gold)))

        # Configure each resource
        trade_config = []
        for i in range(5):
            name = materials_names[i]
            lo, hi = price_limits[i]
            cur_amt = current_amounts[i]
            cur_price = current_prices[i] if i < len(current_prices) else lo
            cur_type = current_types[i] if i < len(current_types) else TRADE_SELL

            status = ""
            if cur_amt > 0:
                action = "Buy" if cur_type == TRADE_BUY else "Sell"
                status = " [Current: {} {} @ {}]".format(action, addThousandSeparator(cur_amt), cur_price)
            print("--- {} ---{}".format(name, status))
            print("  Price range: {} - {}".format(lo, hi))
            print("  (0) Skip  (1) Buy  (2) Sell")
            choice = read(min=0, max=2)

            if choice == 0:
                trade_config.append({
                    "type": None,
                    "amount": 0,
                    "price": cur_price,
                    "total": None,
                    "traded_so_far": 0,
                })
                continue

            trade_type = TRADE_BUY if choice == 1 else TRADE_SELL
            action_name = "buy" if choice == 1 else "sell"

            if choice == 1:
                max_amount = min(MAX_BUY_AMOUNT, gold // lo if lo > 0 else MAX_BUY_AMOUNT)
                print("  Amount to {} [max = {}]:".format(action_name, addThousandSeparator(max_amount)))
            else:
                max_amount = storage_cap
                print("  Amount to {} [max = {}]:".format(action_name, addThousandSeparator(max_amount)))
            amount = read(min=0, max=max_amount)

            if amount == 0:
                trade_config.append({
                    "type": None,
                    "amount": 0,
                    "price": cur_price,
                    "total": None,
                    "traded_so_far": 0,
                })
                continue

            print("  Price per unit [min = {}, max = {}]:".format(lo, hi))
            price = read(min=lo, max=hi)

            trade_config.append({
                "type": trade_type,
                "amount": amount,
                "price": price,
                "total": None,
                "traded_so_far": 0,
            })
            print("")

        # Check if anything was configured
        if not any(cfg["type"] for cfg in trade_config):
            print("\nNo resources configured. Nothing to do.")
            enter()
            event.set()
            return

        # Ask mode
        banner()
        print("Trading mode:")
        print("(1) Continuous - keep refilling offers forever")
        print("(2) Fixed total - stop after trading a set amount")
        mode = read(min=1, max=2)

        if mode == 2:
            for i, cfg in enumerate(trade_config):
                if not cfg["type"]:
                    continue
                action = "buy" if cfg["type"] == TRADE_BUY else "sell"
                print("Total {} to {} [min = {}]:".format(
                    materials_names[i], action, addThousandSeparator(cfg["amount"])
                ))
                total = read(min=cfg["amount"], max=999999999)
                cfg["total"] = total

        # Ask poll interval
        print("\nCheck interval in minutes [15-240, default 60]:")
        interval = read(min=15, max=240)

        # Summary
        banner()
        print("=== Auto Market Trader Summary ===")
        print("City: {}".format(city["name"]))
        print("Interval: {} minutes".format(interval))
        print("")
        for i, cfg in enumerate(trade_config):
            if not cfg["type"]:
                continue
            action = "BUY" if cfg["type"] == TRADE_BUY else "SELL"
            total_str = addThousandSeparator(cfg["total"]) if cfg["total"] else "unlimited"
            print("  {} {}: {} @ {} (total: {})".format(
                action, materials_names[i],
                addThousandSeparator(cfg["amount"]),
                cfg["price"],
                total_str,
            ))
        print("\nProceed? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return

        # Launch background process
        set_child_mode(session)
        event.set()

        info = "Auto Market Trader\n"
        info += "City: {}\n".format(city["name"])
        info += "Interval: {} min\n".format(interval)
        for i, cfg in enumerate(trade_config):
            if cfg["type"]:
                action = "BUY" if cfg["type"] == TRADE_BUY else "SELL"
                info += "  {}: {} {} @ {}\n".format(materials_names[i], action, addThousandSeparator(cfg["amount"]), cfg["price"])
        setInfoSignal(session, info)

        try:
            run_auto_trader(session, city, trade_config, interval)
        except Exception as e:
            msg = "Error in Auto Market Trader:\n{}\nCause:\n{}".format(info, traceback.format_exc())
            sendToBot(session, msg)
        finally:
            session.logout()

    except KeyboardInterrupt:
        event.set()
        return

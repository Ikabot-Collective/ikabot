#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import sys
import traceback

from ikabot import config
from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
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


def _refresh_city(session, city):
    """Re-fetch city data to get current resource levels.
    Returns updated city dict with fresh availableResources etc.
    """
    html = session.get(city_url + city["id"])
    fresh = getCity(html)
    # Preserve marketplace-specific fields
    fresh["pos"] = city["pos"]
    fresh["rango"] = city["rango"]
    return fresh


def buildUpdatePayload(city, trade_config, amounts, existing_amounts, existing_prices, existing_types):
    """Builds the POST payload for updateOffers.
    Preserves existing offers for resources we are not managing.

    Parameters
    ----------
    city : dict
    trade_config : list[dict]
    amounts : list[int]
        The amount to set for each managed resource in this cycle
    existing_amounts : list[int]
        Current amounts on marketplace for all 5 resources
    existing_prices : list[int]
        Current prices for all 5 resources
    existing_types : list[str]
        Current trade types for all 5 resources
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
        if cfg["type"]:
            # This resource is managed by auto-trader
            payload[type_key] = cfg["type"]
            payload[amt_key] = str(amounts[i])
            payload[price_key] = str(cfg["price"])
        else:
            # Preserve existing offer exactly as-is
            payload[type_key] = existing_types[i] if i < len(existing_types) else TRADE_SELL
            payload[amt_key] = str(existing_amounts[i])
            payload[price_key] = str(existing_prices[i])
    return payload


def run_auto_trader(session, city, trade_config, interval_minutes, gold_minimum):
    """Background loop that manages marketplace offers.
    Parameters
    ----------
    session : ikabot.web.session.Session
    city : dict
    trade_config : list[dict]
        List of 5 dicts with keys: type, amount, price, total, traded_so_far, undercut
    interval_minutes : int
    gold_minimum : int
        User-specified minimum gold threshold
    """
    # Get initial gold for 25% safety check
    initial_gold, _ = getGold(session, city)

    # Post initial offers
    html = getMarketInfo(session, city)
    existing_amounts = onSellInMarket(html)
    existing_prices = getOwnOfferPrices(html)
    existing_types = getOwnOfferTradeTypes(html)
    storage_cap = storageCapacityOfMarket(html)

    # Re-fetch price limits (they can change over time)
    price_limits = getPriceLimits(html)

    # Calculate and post initial amounts
    city = _refresh_city(session, city)
    amounts = _calculate_amounts(trade_config, existing_amounts, storage_cap, session, city, gold_minimum, initial_gold, price_limits)
    payload = buildUpdatePayload(city, trade_config, amounts, existing_amounts, existing_prices, existing_types)
    session.post(params=payload)
    last_posted = amounts[:]

    # Startup notification
    msg = "Auto Trader started [{}]:\n".format(city["name"])
    for i, cfg in enumerate(trade_config):
        if cfg["type"]:
            action = "BUY" if cfg["type"] == TRADE_BUY else "SELL"
            total_str = addThousandSeparator(cfg["total"]) if cfg["total"] is not None else "continuous"
            undercut_str = " (undercutting)" if cfg.get("undercut") else ""
            msg += "  {} {}: {} @ {} (target: {}){}\\n".format(
                action, materials_names[i],
                addThousandSeparator(cfg["amount"]),
                cfg["price"], total_str, undercut_str,
            )
    msg += "  Interval: {} min | Gold minimum: {}".format(interval_minutes, addThousandSeparator(gold_minimum))
    sendToBot(session, msg)

    _update_status(session, city, trade_config, "Started")

    while True:
        wait(interval_minutes * 60, maxrandom=60)

        html = getMarketInfo(session, city)
        current_amounts = onSellInMarket(html)
        current_prices = getOwnOfferPrices(html)
        current_types = getOwnOfferTradeTypes(html)
        storage_cap = storageCapacityOfMarket(html)
        price_limits = getPriceLimits(html)

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

                # Per-resource completion notification
                if cfg["total"] is not None and cfg["traded_so_far"] >= cfg["total"]:
                    action = "Bought" if cfg["type"] == TRADE_BUY else "Sold"
                    notifications.append(
                        "TARGET REACHED: {} {} {} (target was {})".format(
                            action,
                            addThousandSeparator(cfg["traded_so_far"]),
                            materials_names[i],
                            addThousandSeparator(cfg["total"]),
                        )
                    )

        # Send notifications if any trades happened
        if notifications:
            msg = "Auto Trader [{}]:\n".format(city["name"])
            msg += "\n".join("  " + n for n in notifications)
            for i, cfg in enumerate(trade_config):
                if cfg["type"] and cfg["total"] is not None:
                    pct = int(cfg["traded_so_far"] * 100 / cfg["total"]) if cfg["total"] > 0 else 100
                    msg += "\n  {}: {}/{} ({}%)".format(
                        materials_names[i],
                        addThousandSeparator(cfg["traded_so_far"]),
                        addThousandSeparator(cfg["total"]),
                        pct,
                    )
            sendToBot(session, msg)

        # Check if all fixed-total resources are complete
        all_done = True
        any_active = False
        for cfg in trade_config:
            if not cfg["type"]:
                continue
            any_active = True
            if cfg["total"] is None:
                all_done = False
                break
            if cfg["traded_so_far"] < cfg["total"]:
                all_done = False
                break
        if all_done and any_active:
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
            # Zero out completed offers
            zero_amounts = [0] * 5
            payload = buildUpdatePayload(city, trade_config, zero_amounts, current_amounts, current_prices, current_types)
            # Only zero managed resources, preserve others
            for i, cfg in enumerate(trade_config):
                if cfg["type"]:
                    amt_key = RESOURCE_PARAMS[i][0]
                    payload[amt_key] = "0"
            session.post(params=payload)
            return

        # Handle undercutting: update prices if enabled
        for i, cfg in enumerate(trade_config):
            if not cfg["type"] or not cfg.get("undercut"):
                continue
            lo, hi = price_limits[i]
            if cfg["type"] == TRADE_SELL:
                # Scan sell offers, undercut lowest by 1
                lowest = scanMarketPrices(session, city, i, "444")
                if lowest is not None and lowest > lo:
                    new_price = max(lo, lowest - 1)
                    if new_price != cfg["price"]:
                        cfg["price"] = new_price
            else:
                # Scan buy offers, outbid highest by 1
                highest = scanMarketPrices(session, city, i, "333")
                if highest is not None and highest < hi:
                    new_price = min(hi, highest + 1)
                    if new_price != cfg["price"]:
                        cfg["price"] = new_price

        # Refresh city data for available resources
        city = _refresh_city(session, city)

        # Recalculate and refill offers
        amounts = _calculate_amounts(
            trade_config, current_amounts, storage_cap,
            session, city, gold_minimum, initial_gold, price_limits
        )
        payload = buildUpdatePayload(city, trade_config, amounts, current_amounts, current_prices, current_types)
        session.post(params=payload)
        last_posted = amounts[:]

        _update_status(session, city, trade_config, getDateTime())


def _calculate_amounts(trade_config, current_amounts, storage_cap, session, city, gold_minimum, initial_gold, price_limits):
    """Calculate the amounts to post for each resource.
    Parameters
    ----------
    trade_config : list[dict]
    current_amounts : list[int]
    storage_cap : int
    session : ikabot.web.session.Session
    city : dict
    gold_minimum : int
        User-specified gold floor
    initial_gold : int
        Gold at start for 25% safety check
    price_limits : list[tuple[int, int]]
    Returns
    -------
    amounts : list[int]
    """
    amounts = [0] * 5

    # First pass: calculate sell amounts (they share storage)
    # Account for non-managed resources already in storage
    used_storage = 0
    for i, cfg in enumerate(trade_config):
        if not cfg["type"]:
            # Non-managed resources take storage space too
            used_storage += current_amounts[i]
    available_storage = max(0, storage_cap - used_storage)

    total_sell = 0
    for i, cfg in enumerate(trade_config):
        if cfg["type"] == TRADE_SELL:
            desired = cfg["amount"]
            if cfg["total"] is not None:
                remaining = max(0, cfg["total"] - cfg["traded_so_far"])
                desired = min(desired, remaining)
            # Limit by city's available resources
            city_available = city["availableResources"][i] if i < len(city.get("availableResources", [])) else 0
            desired = min(desired, city_available)
            amounts[i] = desired
            total_sell += desired

    # Enforce storage capacity for sell orders
    if total_sell > available_storage:
        ratio = available_storage / total_sell if total_sell > 0 else 0
        for i, cfg in enumerate(trade_config):
            if cfg["type"] == TRADE_SELL:
                amounts[i] = int(amounts[i] * ratio)

    # Second pass: calculate buy amounts (they use gold)
    gold, _ = getGold(session, city)
    # Apply gold minimum threshold
    spendable_gold = max(0, gold - gold_minimum)

    for i, cfg in enumerate(trade_config):
        if cfg["type"] == TRADE_BUY:
            desired = cfg["amount"]
            if cfg["total"] is not None:
                remaining = max(0, cfg["total"] - cfg["traded_so_far"])
                desired = min(desired, remaining)
            desired = min(desired, MAX_BUY_AMOUNT)
            # Limit by spendable gold
            if cfg["price"] > 0:
                affordable = spendable_gold // cfg["price"]
                desired = min(desired, affordable)
                cost = desired * cfg["price"]
                spendable_gold -= cost
                # 25% safety check: would this order reduce gold below 25% of initial?
                if gold - cost < initial_gold * 0.25 and desired > 0:
                    # Reduce to stay above 25%
                    safe_spend = max(0, gold - int(initial_gold * 0.25))
                    safe_amount = safe_spend // cfg["price"] if cfg["price"] > 0 else 0
                    if safe_amount < desired:
                        # Adjust back
                        spendable_gold += cost
                        desired = safe_amount
                        spendable_gold -= desired * cfg["price"]
            # Check city warehouse space for incoming bought resources
            free_space = city["freeSpaceForResources"][i] if i < len(city.get("freeSpaceForResources", [])) else 0
            desired = min(desired, free_space)
            amounts[i] = desired

    return amounts


def _update_status(session, city, trade_config, timestamp):
    """Update the process status line with running totals."""
    parts = []
    for i, cfg in enumerate(trade_config):
        if not cfg["type"]:
            continue
        action = "BUY" if cfg["type"] == TRADE_BUY else "SELL"
        name = materials_names[i][:3]
        if cfg["total"] is not None:
            pct = int(cfg["traded_so_far"] * 100 / cfg["total"]) if cfg["total"] > 0 else 100
            parts.append("{} {}:{}/{} ({}%)".format(
                action, name,
                addThousandSeparator(cfg["traded_so_far"]),
                addThousandSeparator(cfg["total"]),
                pct,
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
        gold, gold_production = getGold(session, city)

        # Refresh city data for resource display
        city = _refresh_city(session, city)

        print("City: {}".format(city["name"]))
        print("Trading Post storage: {}".format(addThousandSeparator(storage_cap)))
        print("Gold: {} (production: {}/hr)".format(addThousandSeparator(gold), addThousandSeparator(gold_production)))
        print("")

        # Show city resources
        print("City resources:")
        for i in range(5):
            avail = city["availableResources"][i] if i < len(city.get("availableResources", [])) else 0
            free = city["freeSpaceForResources"][i] if i < len(city.get("freeSpaceForResources", [])) else 0
            print("  {}: {} available, {} free warehouse space".format(
                materials_names[i],
                addThousandSeparator(avail),
                addThousandSeparator(free),
            ))
        print("")

        # Show existing offers
        has_existing = any(a > 0 for a in current_amounts)
        if has_existing:
            print("Current marketplace offers:")
            for i in range(5):
                if current_amounts[i] > 0:
                    t = "Buy" if (i < len(current_types) and current_types[i] == TRADE_BUY) else "Sell"
                    p = current_prices[i] if i < len(current_prices) else 0
                    print("  {}: {} {} @ {}".format(materials_names[i], t, addThousandSeparator(current_amounts[i]), p))
            print("")

        # Ask what to do with existing offers
        if has_existing:
            print("What would you like to do with existing offers?")
            print("(1) Keep them and configure new auto-trading alongside")
            print("(2) Remove specific offers first")
            print("(3) Clear all offers and start fresh")
            choice = read(min=1, max=3)

            if choice == 2:
                # Let user remove individual offers
                for i in range(5):
                    if current_amounts[i] > 0:
                        t = "Buy" if (i < len(current_types) and current_types[i] == TRADE_BUY) else "Sell"
                        p = current_prices[i] if i < len(current_prices) else 0
                        print("Remove {} {} @ {}? [y/N]".format(
                            t, materials_names[i], p
                        ))
                        rta = read(values=["y", "Y", "n", "N", ""])
                        if rta.lower() == "y":
                            current_amounts[i] = 0
                # Post the cleared offers
                clear_payload = {
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
                    clear_payload[type_key] = current_types[i] if i < len(current_types) else TRADE_SELL
                    clear_payload[amt_key] = str(current_amounts[i])
                    clear_payload[price_key] = str(current_prices[i]) if i < len(current_prices) else "1"
                session.post(params=clear_payload)
                # Refresh
                html = getMarketInfo(session, city)
                current_amounts = onSellInMarket(html)
                current_prices = getOwnOfferPrices(html)
                current_types = getOwnOfferTradeTypes(html)
                print("Offers updated.\n")

            elif choice == 3:
                # Clear all
                clear_payload = {
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
                    clear_payload[type_key] = TRADE_SELL
                    clear_payload[amt_key] = "0"
                    clear_payload[price_key] = str(current_prices[i]) if i < len(current_prices) else "1"
                session.post(params=clear_payload)
                current_amounts = [0, 0, 0, 0, 0]
                # Refresh
                html = getMarketInfo(session, city)
                current_prices = getOwnOfferPrices(html)
                current_types = getOwnOfferTradeTypes(html)
                print("All offers cleared.\n")

            banner()

        # Track shared budgets during setup
        remaining_storage = storage_cap - sum(
            current_amounts[i] for i in range(5)
        )
        remaining_gold = gold

        # Configure each resource
        trade_config = []
        for i in range(5):
            name = materials_names[i]
            lo, hi = price_limits[i]
            cur_amt = current_amounts[i]
            cur_price = current_prices[i] if i < len(current_prices) else lo
            cur_type = current_types[i] if i < len(current_types) else TRADE_SELL
            city_avail = city["availableResources"][i] if i < len(city.get("availableResources", [])) else 0
            city_free = city["freeSpaceForResources"][i] if i < len(city.get("freeSpaceForResources", [])) else 0

            status = ""
            if cur_amt > 0:
                action = "Buy" if cur_type == TRADE_BUY else "Sell"
                status = " [Active: {} {} @ {}]".format(action, addThousandSeparator(cur_amt), cur_price)
            print("--- {} ---{}".format(name, status))
            print("  City: {} available | {} free warehouse space".format(
                addThousandSeparator(city_avail), addThousandSeparator(city_free),
            ))
            print("  Price range: {} - {}".format(lo, hi))
            print("  Remaining storage budget: {} | Remaining gold budget: {}".format(
                addThousandSeparator(remaining_storage), addThousandSeparator(remaining_gold),
            ))
            print("  (0) Skip  (1) Buy  (2) Sell")
            choice = read(min=0, max=2)

            if choice == 0:
                trade_config.append({
                    "type": None,
                    "amount": 0,
                    "price": cur_price,
                    "total": None,
                    "traded_so_far": 0,
                    "undercut": False,
                })
                continue

            trade_type = TRADE_BUY if choice == 1 else TRADE_SELL
            action_name = "buy" if choice == 1 else "sell"

            if choice == 1:
                max_amount = min(MAX_BUY_AMOUNT, remaining_gold // lo if lo > 0 else MAX_BUY_AMOUNT, city_free)
                print("  Amount to {} per cycle [max = {}]:".format(action_name, addThousandSeparator(max_amount)))
            else:
                max_amount = min(remaining_storage, city_avail)
                print("  Amount to {} per cycle [max = {}]:".format(action_name, addThousandSeparator(max_amount)))
            amount = read(min=0, max=max_amount)

            if amount == 0:
                trade_config.append({
                    "type": None,
                    "amount": 0,
                    "price": cur_price,
                    "total": None,
                    "traded_so_far": 0,
                    "undercut": False,
                })
                continue

            # Ask about undercutting/outbidding
            print("  Set price manually or auto-undercut/outbid?")
            print("  (1) Set price manually")
            if choice == 2:
                print("  (2) Auto-undercut (scan market each cycle, beat lowest seller by 1)")
            else:
                print("  (2) Auto-outbid (scan market each cycle, beat highest buyer by 1)")
            price_mode = read(min=1, max=2)

            undercut = False
            if price_mode == 1:
                print("  Price per unit [min = {}, max = {}]:".format(lo, hi))
                price = read(min=lo, max=hi)
            else:
                undercut = True
                # Scan market for initial price
                if choice == 2:
                    scanned = scanMarketPrices(session, city, i, "444")
                    if scanned is not None and scanned > lo:
                        price = max(lo, scanned - 1)
                        print("  Current lowest sell: {} -> your price: {}".format(scanned, price))
                    else:
                        print("  No sell offers found. Set starting price [min = {}, max = {}]:".format(lo, hi))
                        price = read(min=lo, max=hi)
                else:
                    scanned = scanMarketPrices(session, city, i, "333")
                    if scanned is not None and scanned < hi:
                        price = min(hi, scanned + 1)
                        print("  Current highest buy: {} -> your price: {}".format(scanned, price))
                    else:
                        print("  No buy offers found. Set starting price [min = {}, max = {}]:".format(lo, hi))
                        price = read(min=lo, max=hi)

            # Update budget tracking
            if choice == 2:
                remaining_storage -= amount
            else:
                remaining_gold -= amount * price

            trade_config.append({
                "type": trade_type,
                "amount": amount,
                "price": price,
                "total": None,
                "traded_so_far": 0,
                "undercut": undercut,
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
        interval_input = read(min=15, max=240, empty=True)
        interval = int(interval_input) if interval_input != "" else 60

        # Ask gold minimum threshold
        print("\nMinimum gold to keep (won't spend below this) [default 0]:")
        gold_min_input = read(min=0, max=gold, empty=True)
        gold_minimum = int(gold_min_input) if gold_min_input != "" else 0

        # Summary
        banner()
        print("=== Auto Market Trader Summary ===")
        print("City: {}".format(city["name"]))
        print("Interval: {} minutes".format(interval))
        print("Gold minimum: {}".format(addThousandSeparator(gold_minimum)))
        print("")
        for i, cfg in enumerate(trade_config):
            if not cfg["type"]:
                continue
            action = "BUY" if cfg["type"] == TRADE_BUY else "SELL"
            total_str = addThousandSeparator(cfg["total"]) if cfg["total"] else "continuous"
            undercut_str = " [auto-undercut]" if cfg.get("undercut") else ""
            print("  {} {}: {} @ {} (total: {}){}".format(
                action, materials_names[i],
                addThousandSeparator(cfg["amount"]),
                cfg["price"],
                total_str,
                undercut_str,
            ))
        print("\nNote: Existing offers for unconfigured resources will be preserved.")
        print("Gold safety: Orders won't reduce gold below {} or 25% of starting gold.".format(
            addThousandSeparator(gold_minimum)
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
        info += "Gold minimum: {}\n".format(addThousandSeparator(gold_minimum))
        for i, cfg in enumerate(trade_config):
            if cfg["type"]:
                action = "BUY" if cfg["type"] == TRADE_BUY else "SELL"
                undercut_str = " [auto-undercut]" if cfg.get("undercut") else ""
                info += "  {}: {} {} @ {}{}\n".format(
                    materials_names[i], action,
                    addThousandSeparator(cfg["amount"]),
                    cfg["price"], undercut_str,
                )
        setInfoSignal(session, info)

        try:
            run_auto_trader(session, city, trade_config, interval, gold_minimum)
        except Exception as e:
            msg = "Error in Auto Market Trader:\n{}\nCause:\n{}".format(info, traceback.format_exc())
            sendToBot(session, msg)
        finally:
            session.logout()

    except KeyboardInterrupt:
        event.set()
        return


# --- Future Enhancement: Pause/Resume ---
# Concept: Save trade_config + state to a JSON file keyed by city ID.
# On startup, check if a saved state exists and offer to resume.
# The save file would store: trade_config (with traded_so_far),
# interval_minutes, gold_minimum, and a timestamp.
# This would allow the user to stop the process and restart it
# without losing progress on fixed-total trades.
# Not implemented yet as the mechanism for persisting state across
# process restarts needs careful design (file locking, stale state
# detection, etc).

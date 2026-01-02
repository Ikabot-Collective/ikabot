#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import traceback
import time
import datetime
import json
import os
import re

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity, getIsland
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import executeRoutes
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.naval import getAvailableShips, getAvailableFreighters
from ikabot.helpers.varios import addThousandSeparator, getDateTime


def print_module_banner(page_title=None):
    """
    Print the Resource Transport Manager banner with optional page title
    
    Parameters
    ----------
    page_title : str, optional
        The current page/section title to display below the banner
    """
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║            RESOURCE TRANSPORT MANAGER                     ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    if page_title:
        print(f"\n{page_title}")
        print("──────────────────────────────────────────────────────────")
    print("")


def get_lock_file_path(session, use_freighters=False):
    """
    Get the path to the SHARED shipping lock file
    Uses a standardized naming convention for ship locks that can be shared across ALL scripts
    
    Lock file format: .ikabot_shared_{ship_type}_{server}_{username}.lock
    - merchant_ships: .ikabot_shared_merchant_ships_s1-en_PlayerOne.lock
    - freighters: .ikabot_shared_freighters_s1-en_PlayerOne.lock
    
    Any script using ships should use this same naming convention to coordinate properly.
    
    Parameters
    ----------
    session : ikabot.web.session.Session
    use_freighters : bool
    
    Returns
    -------
    lock_file_path : str
    """
    ship_type = "freighters" if use_freighters else "merchant_ships"
    # Sanitize server and username to be filesystem-safe
    safe_server = session.servidor.replace('/', '_').replace('\\', '_')
    safe_username = session.username.replace('/', '_').replace('\\', '_')
    # SHARED lock file format - recognized by all scripts
    lock_filename = f".ikabot_shared_{ship_type}_{safe_server}_{safe_username}.lock"
    return os.path.join(os.path.expanduser("~"), lock_filename)



def acquire_shipping_lock(session, use_freighters=False, timeout=300):
    """
    Try to acquire shipping lock, wait up to timeout seconds
    
    Parameters
    ----------
    session : ikabot.web.session.Session
    use_freighters : bool
        If True, use freighter lock file, otherwise use merchant lock file
    timeout : int
        Maximum seconds to wait for lock
    
    Returns
    -------
    success : bool
        True if lock acquired, False if timeout
    """
    lock_file = get_lock_file_path(session, use_freighters)
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Try to check if lock file exists
            if not os.path.exists(lock_file):
                # Create lock file
                with open(lock_file, 'w') as f:
                    lock_data = {
                        'pid': os.getpid(),
                        'timestamp': time.time(),
                        'ship_type': 'freighters' if use_freighters else 'merchant_ships',
                        'server': session.servidor,
                        'username': session.username
                    }
                    json.dump(lock_data, f)
                return True
            else:
                # Lock exists, check if it's stale (older than 10 minutes)
                try:
                    with open(lock_file, 'r') as f:
                        lock_data = json.load(f)
                        if time.time() - lock_data['timestamp'] > 600:
                            # Stale lock, remove it
                            os.remove(lock_file)
                            continue
                except:
                    # Corrupted lock file, remove it
                    try:
                        os.remove(lock_file)
                    except:
                        pass
                    continue
        except Exception as e:
            pass
        
        # Wait before trying again
        time.sleep(5)
    
    return False  # Timeout


def release_shipping_lock(session, use_freighters=False):
    """
    Release the shipping lock by deleting the lock file
    
    Parameters
    ----------
    session : ikabot.web.session.Session
    use_freighters : bool
        If True, release freighter lock, otherwise release merchant lock
    """
    lock_file = get_lock_file_path(session, use_freighters)
    try:
        if os.path.exists(lock_file):
            # Verify this process owns the lock before removing
            try:
                with open(lock_file, 'r') as f:
                    lock_data = json.load(f)
                    if lock_data['pid'] == os.getpid():
                        os.remove(lock_file)
            except:
                # If we can't read it, just try to remove it
                os.remove(lock_file)
    except Exception as e:
        pass


def readResourceAmount(resource_name):
    """
    Read a resource amount with automatic comma formatting display
    Returns None for blank (ignore), an integer value, 'EXIT' for exit request, or 'RESTART' to restart section
    
    Parameters
    ----------
    resource_name : str
        The name of the resource being configured
    
    Returns
    -------
    amount : int or None or str ('EXIT' or 'RESTART')
    """
    while True:
        user_input = read(msg=f"{resource_name}: ", empty=True, additionalValues=["'", "="])
        
        # Exit request
        if user_input == "'":
            return 'EXIT'
        
        # Restart request
        if user_input == "=":
            return 'RESTART'
        
        # Blank means ignore this resource
        if user_input == "":
            return None
        
        # Remove any commas the user might have typed
        cleaned_input = user_input.replace(",", "").replace(" ", "")
        
        # Check if it's a valid number
        if cleaned_input.isdigit():
            amount = int(cleaned_input)
            # Display the formatted version so user can see it with commas
            if amount > 0:
                print(f"  → Set to: {addThousandSeparator(amount)}")
            return amount
        else:
            print("  Please enter a number, 0, leave blank, or press ' to exit")


def resourceTransportManager(session, event, stdin_fd, predetermined_input):
    """
    Resource Transport Manager - Main entry point
    
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
        # Check telegram with skip option
        telegram_enabled = checkTelegramData(session)
        if telegram_enabled is False:
            print_module_banner()
            print("Telegram notifications are not configured.")
            print("Do you want to continue without notifications? [Y/n]")
            rta = read(values=["y", "Y", "n", "N", ""])
            if rta.lower() == "n":
                event.set()
                return
            # User chose to skip telegram
            telegram_enabled = None  # Mark as intentionally skipped
        
        print_module_banner("Shipping Mode Selection")
        
        # Choose shipping mode
        print("Select shipping mode:")
        print("(1) Consolidate/Single Shipments: Multiple cities → One destination")
        print("(2) Distribute: One city → Multiple destinations")
        print("(') Back to main menu")
        shipping_mode = read(min=1, max=2, digit=True, additionalValues=["'"])
        if shipping_mode == "'":
            event.set()
            return
        
        if shipping_mode == 1:
            # Existing consolidate mode
            consolidateMode(session, event, stdin_fd, predetermined_input, telegram_enabled)
        else:
            # New distribute mode
            distributeMode(session, event, stdin_fd, predetermined_input, telegram_enabled)
            
    except KeyboardInterrupt:
        event.set()
        return


def consolidateMode(session, event, stdin_fd, predetermined_input, telegram_enabled):
    """
    Multiple source cities → Single destination city
    """
    try:
        print_module_banner("Ship Type Selection")
        
        # Choose ship type
        print("What type of ships do you want to use?")
        print("(1) Merchant ships")
        print("(2) Freighters")
        print("(') Back to main menu")
        shiptype = read(min=1, max=2, digit=True, additionalValues=["'"])
        if shiptype == "'":
            event.set()
            return
        useFreighters = (shiptype == 2)
        
        print_module_banner("Source City Selection")
        
        # Get and choose source city/cities
        print("Select source city option:")
        print("(1) Single city")
        print("(2) Multiple cities")
        print("(') Back to main menu")
        source_option = read(min=1, max=2, digit=True, additionalValues=["'"])
        if source_option == "'":
            event.set()
            return
        
        origin_cities = []
        if source_option == 1:
            # Single city
            print_module_banner("Single Source City")
            print("Select source city:")
            print("Island Luxury: (W) Wine | (M) Marble | (C) Crystal | (S) Sulfur")
            print("")
            origin_city = chooseCity(session)
            origin_cities.append(origin_city)
        else:
            # Multiple cities
            print_module_banner("Multiple Source Cities")
            source_msg = 'Select source cities (cities to send resources from):'
            source_city_ids, source_cities_dict = ignoreCities(session, msg=source_msg)
            
            if not source_city_ids:
                print("No cities selected!")
                enter()
                event.set()
                return
            
            # Get full city data for each selected city
            for city_id in source_city_ids:
                html = session.get(city_url + city_id)
                city = getCity(html)
                origin_cities.append(city)
        
        print_module_banner("Sending Mode Selection")
        
        # Create source cities summary
        if len(origin_cities) == 1:
            source_cities_summary = origin_cities[0]['name']
        else:
            source_cities_summary = ', '.join([city['name'] for city in origin_cities])
        
        print(f"Source cities: {source_cities_summary}")
        print("")
        print("Choose sending mode:")
        print("(1) Send ALL resources EXCEPT a reserve amount (keep X, send rest)")
        print("(2) Send SPECIFIC amounts (send exactly X)")
        print("(') Back to main menu")
        send_mode = read(min=1, max=2, digit=True, additionalValues=["'"])
        if send_mode == "'":
            event.set()
            return
        
        print_module_banner("Resource Configuration")
        print(f"Source cities: {source_cities_summary}")
        print("")
        
        if send_mode == 1:
            print("Configure resource reserves (KEEP mode):")
            print("(Enter a number to keep that amount in reserve)")
            print("(Enter 0 to send ALL of that resource)")
            print("(Leave blank to IGNORE that resource - won't send it)")
            print("(You can type with or without commas - e.g., 6000 or 6,000)")
            print("(Press '=' to restart resource configuration from beginning)")
            print("(Press ' to return to main menu)")
            print("")
        else:
            print("Configure resource amounts to send (SEND mode):")
            print("(Enter a number to send that specific amount)")
            print("(Enter 0 or leave blank to NOT send that resource)")
            print("(You can type with or without commas - e.g., 6000 or 6,000)")
            print("(Press '=' to restart resource configuration from beginning)")
            print("(Press ' to return to main menu)")
            print("")
            
            # Show available resources for single source city
            if len(origin_cities) == 1:
                html = session.get(city_url + str(origin_cities[0]['id']))
                single_city_data = getCity(html)
                print(f"Available resources in {origin_cities[0]['name']}:")
                # Header row with resource names
                header = "  "
                for resource in materials_names:
                    header += f"{resource:>12}  "
                print(header)
                # Separator row
                separator = "  "
                for _ in materials_names:
                    separator += f"{'-'*12}  "
                print(separator)
                # Amount row
                amounts = "  "
                for i in range(len(materials_names)):
                    amount = single_city_data['availableResources'][i]
                    amounts += f"{addThousandSeparator(amount):>12}  "
                print(amounts)
                print("")
        
        # Get resource reserves or send amounts (with restart support)
        resource_config_complete = False
        while not resource_config_complete:
            resource_config = []
            restart = False
            
            for i, resource in enumerate(materials_names):
                amount = readResourceAmount(resource)
                
                if amount == 'EXIT':
                    event.set()
                    return
                
                # Check if user wants to restart
                if amount == 'RESTART':
                    print("\nRestarting resource configuration...\n")
                    restart = True
                    break
                
                resource_config.append(amount)
            
            if not restart:
                resource_config_complete = True
        
        banner()
        print(f"Source cities: {source_cities_summary}")
        print("")
        print("Resource configuration:")
        if send_mode == 1:
            for i, resource in enumerate(materials_names):
                if resource_config[i] is None:
                    print(f"  {resource}: IGNORED (won't send)")
                elif resource_config[i] == 0:
                    print(f"  {resource}: Send ALL")
                else:
                    print(f"  {resource}: Keep {addThousandSeparator(resource_config[i])}, send excess")
        else:
            for i, resource in enumerate(materials_names):
                if resource_config[i] is None or resource_config[i] == 0:
                    print(f"  {resource}: NOT sending")
                else:
                    print(f"  {resource}: Send {addThousandSeparator(resource_config[i])}")
        print("")
        
        print_module_banner("Destination Selection")
        
        print(f"Source cities: {source_cities_summary}")
        print("")
        print("Select destination type:")
        print("(1) Internal city (choose from your cities)")
        print("(2) External city (enter island coordinates)")
        print("(') Back to main menu")
        destination_type = read(min=1, max=2, digit=True, additionalValues=["'"])
        if destination_type == "'":
            event.set()
            return
        
        if destination_type == 2:
            # External city - get island coordinates (with restart support)
            coords_complete = False
            while not coords_complete:
                print_module_banner("Island Coordinates & City Selection")
                print("Enter destination island coordinates:")
                print("(Press '=' to restart coordinate entry)")
                print("(Press ' at any prompt to return to main menu)")
                
                x_coord = read(msg="X coordinate: ", digit=True, additionalValues=["'", "="])
                if x_coord == "'":
                    event.set()
                    return
                
                if x_coord == "=":
                    print("\nRestarting coordinate entry...\n")
                    continue
                
                y_coord = read(msg="Y coordinate: ", digit=True, additionalValues=["'", "="])
                if y_coord == "'":
                    event.set()
                    return
                
                if y_coord == "=":
                    print("\nRestarting coordinate entry...\n")
                    continue
                
                island_coords = f"xcoord={x_coord}&ycoord={y_coord}"
                html = session.get(f"view=island&{island_coords}")
                island = getIsland(html)
                
                # Get all cities on the island
                cities_on_island = [city for city in island["cities"] if city["type"] == "city"]
                
                if len(cities_on_island) == 0:
                    print(f"Island {x_coord}:{y_coord} has no cities!")
                    enter()
                    # Don't exit, let them try again
                    continue
                
                print("")
                print(f"Island: {island['name']} [{island['x']}:{island['y']}]")
                print(f"Resource: {materials_names[int(island['tradegood'])]}")
                print("")
                print("Select destination city:")
                print("(0) Exit")
                print("(=) Restart coordinate entry")
                print("(') Back to main menu")
                print("")
                
                # Print table header
                print(f"    {'City Name':<20} {'Player':<15}")
                print(f"    {'-'*20} {'-'*15}")
                
                for i, city in enumerate(cities_on_island):
                    city_num = i + 1
                    player_name = city.get('Name', 'Unknown')
                    city_name = city.get('name', 'Unknown')
                    
                    # Truncate city name to 20 characters
                    if len(city_name) > 20:
                        city_name_display = city_name[:17] + "..."
                    else:
                        city_name_display = city_name
                    
                    # Truncate player name to 15 characters
                    if len(player_name) > 15:
                        player_name_display = player_name[:12] + "..."
                    else:
                        player_name_display = player_name
                    
                    # Format: (1) CityName           PlayerName
                    print(f"({city_num:>2}) {city_name_display:<20} {player_name_display:<15}")
                
                print("")
                city_choice = read(min=0, max=len(cities_on_island), additionalValues=["'", "="])
                
                if city_choice == 0 or city_choice == "'":
                    event.set()
                    return
                
                if city_choice == "=":
                    print("\nRestarting coordinate entry...\n")
                    continue  # Go back to start of loop
                
                # Get the selected city (subtract 1 for 0-based index)
                destination_city_data = cities_on_island[city_choice - 1]
                destination_city_id = destination_city_data["id"]
                
                # Get full city data
                html = session.get(city_url + str(destination_city_id))
                destination_city = getCity(html)
                destination_city["isOwnCity"] = destination_city_data.get("state", "") == "" and destination_city_data.get("Name", "") == session.username
                
                # Confirm city selection
                print("")
                print(f"Selected: {destination_city['name']}")
                print(f"Player: {destination_city_data.get('Name', 'Unknown')}")
                print(f"Island: {island['name']} [{island['x']}:{island['y']}]")
                print("")
                print("Confirm this destination? [Y/n]")
                print("(Press '=' to restart coordinate entry)")
                confirm = read(values=["y", "Y", "n", "N", "", "="])
                
                if confirm == "=":
                    print("\nRestarting coordinate entry...\n")
                    continue
                
                if confirm.lower() == "n":
                    print("\nReselecting city...\n")
                    continue  # Stay in the city selection loop
                
                # Successfully selected and confirmed, exit loop
                coords_complete = True
            
        else:
            # Internal city - choose from user's cities
            print_module_banner("Internal City Selection")
            print("Select destination city from your cities:")
            print("Island Luxury: (W) Wine | (M) Marble | (C) Crystal | (S) Sulfur")
            print("")
            destination_city = chooseCity(session)
            
            # Get the island data for this city
            html = session.get(city_url + str(destination_city['id']))
            destination_city = getCity(html)
            island_id = destination_city['islandId']
            
            # Get island information
            html = session.get(island_url + island_id)
            island = getIsland(html)
            
            destination_city["isOwnCity"] = True
        
        # Display destination info
        if destination_type == 2:
            # External city - use destination_city_data for player name
            player_name = destination_city_data.get('Name', 'Unknown')
        else:
            # Internal city - it's your own city
            player_name = session.username
        
        print(f"Destination city: {destination_city['name']} (Player: {player_name})")
        print(f"Island: {island['name']} [{island['x']}:{island['y']}]")
        print("")
        
        # AUTOMATICALLY EXCLUDE destination city from origin cities if present
        original_count = len(origin_cities)
        origin_cities = [city for city in origin_cities if city['id'] != destination_city['id']]
        excluded_count = original_count - len(origin_cities)
        
        if excluded_count > 0:
            print(f"⚠️  Automatically excluded destination city '{destination_city['name']}' from source cities")
            print("")
        
        # Check if we still have source cities
        if len(origin_cities) == 0:
            print("Error: No source cities remaining after excluding destination!")
            print("The destination city was your only source city.")
            enter()
            event.set()
            return
        
        # Ask about notifications BEFORE schedule (only if telegram is configured)
        if telegram_enabled is None:
            # User already declined telegram at the start, skip notification preferences
            notify_on_start = False
        else:
            print_module_banner("Notification Preferences")
            print("When do you want to receive Telegram notifications?")
            print("(1) Partial - When new scheduled shipment is dispatched - Total Resources to be sent")
            print("(2) All - Every Individual Shipment - can get cluttered")
            print("(3) None - No notifications")
            print("(') Back to main menu")
            notif_choice = read(min=1, max=3, digit=True, additionalValues=["'"])
            if notif_choice == "'":
                event.set()
                return
            
            # Set notification mode
            if notif_choice == 1:
                telegram_enabled = None  # No regular notifications
                notify_on_start = True  # Only start notifications
            elif notif_choice == 2:
                telegram_enabled = True  # All notifications
                notify_on_start = True
            else:  # notif_choice == 3
                telegram_enabled = None  # No notifications
                notify_on_start = False
        
        print_module_banner("Schedule Configuration")
        
        # Ask for interval
        print("How often should resources be sent (in hours)?")
        print("(0 for one-time shipment, or minimum every (1) hour for recurring)")
        print("(Press ' to return to main menu)")
        interval_hours = read(min=0, digit=True, additionalValues=["'"])
        if interval_hours == "'":
            event.set()
            return
        
        print_module_banner("Configuration Summary")
        
        # Calculate total resources to be sent from all cities
        total_resources_to_send = [0] * len(materials_names)
        grand_total = 0
        
        for origin_city in origin_cities:
            html = session.get(city_url + str(origin_city['id']))
            origin_city_data = getCity(html)
            
            for i, resource in enumerate(materials_names):
                if resource_config[i] is None:
                    continue
                
                available = origin_city_data['availableResources'][i]
                
                if send_mode == 1:
                    if resource_config[i] == 0:
                        sendable = available
                    else:
                        sendable = max(0, available - resource_config[i])
                else:
                    if resource_config[i] == 0:
                        sendable = 0
                    else:
                        sendable = min(resource_config[i], available)
                
                total_resources_to_send[i] += sendable
                grand_total += sendable
        
        print(f"Configuration:")
        print(f"  Ship type: {'Freighters' if useFreighters else 'Merchant ships'}")
        print(f"  Mode: {'Send all except reserves' if send_mode == 1 else 'Send specific amounts'}")
        print(f"")
        print(f"  Source cities ({len(origin_cities)}):")
        for city in origin_cities:
            print(f"    - {city['name']}")
        print(f"")
        print(f"  Destination:")
        print(f"    - {destination_city['name']} on island {island['x']}:{island['y']}")
        print(f"")
        print(f"  Resource Configuration:")
        if send_mode == 1:
            for i, resource in enumerate(materials_names):
                if resource_config[i] is None:
                    print(f"    {resource:<10} IGNORED")
                elif resource_config[i] == 0:
                    print(f"    {resource:<10} Send ALL")
                else:
                    print(f"    {resource:<10} Keep {addThousandSeparator(resource_config[i])}")
        else:
            for i, resource in enumerate(materials_names):
                if resource_config[i] is None or resource_config[i] == 0:
                    print(f"    {resource:<10} NOT sending")
                else:
                    print(f"    {resource:<10} Send {addThousandSeparator(resource_config[i])}")
        
        print(f"")
        print(f"  Total Resources to Send:")
        print(f"    {'Resource':<10} {'Amount':>15}")
        print(f"    {'-'*10} {'-'*15}")
        for i, resource in enumerate(materials_names):
            if total_resources_to_send[i] > 0:
                print(f"    {resource:<10} {addThousandSeparator(total_resources_to_send[i]):>15}")
        print(f"    {'-'*10} {'-'*15}")
        print(f"    {'TOTAL':<10} {addThousandSeparator(grand_total):>15}")
        
        print(f"")
        print(f"  Interval: {interval_hours} hour(s)" if interval_hours > 0 else "  Mode: One-time shipment")
        
        print("")
        print("Proceed? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return
        
        enter()
        
    except KeyboardInterrupt:
        event.set()
        return
    
    set_child_mode(session)
    event.set()
    
    info = f"\nAuto-send resources from {source_cities_summary} to {destination_city['name']} every {interval_hours} hour(s)\n"
    setInfoSignal(session, info)
    
    try:
        do_it(session, origin_cities, destination_city, island, interval_hours, resource_config, useFreighters, send_mode, telegram_enabled, notify_on_start)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def distributeMode(session, event, stdin_fd, predetermined_input, telegram_enabled):
    """
    Single source city → Multiple destination cities
    """
    try:
        print_module_banner("Ship Type Selection")
        
        # Choose ship type
        print("What type of ships do you want to use?")
        print("(1) Merchant ships")
        print("(2) Freighters")
        print("(') Back to main menu")
        shiptype = read(min=1, max=2, digit=True, additionalValues=["'"])
        if shiptype == "'":
            event.set()
            return
        useFreighters = (shiptype == 2)
        
        print_module_banner("Source City Selection")
        
        # Get source city
        print("Select source city:")
        print("Island Luxury: (W) Wine | (M) Marble | (C) Crystal | (S) Sulfur")
        print("")
        origin_city = chooseCity(session)
        
        banner()
        
        # Get destination cities (source city will be automatically excluded)
        print(f"Source city: {origin_city['name']}")
        print("")
        print("Note: Source city will be automatically excluded from destinations")
        print("")
        dest_msg = 'Select destination cities (cities to receive resources):'
        destination_city_ids, destination_cities_dict = ignoreCities(session, msg=dest_msg)
        
        # Remove source city from destinations if it was selected
        source_city_id = str(origin_city['id'])
        if source_city_id in destination_city_ids:
            destination_city_ids.remove(source_city_id)
            print(f"Removed {origin_city['name']} from destinations (source city cannot send to itself)")
        
        if not destination_city_ids:
            print("No valid destination cities selected!")
            enter()
            event.set()
            return
        
        # Get full city data for each destination
        destination_cities = []
        for city_id in destination_city_ids:
            html = session.get(city_url + city_id)
            city = getCity(html)
            destination_cities.append(city)
        
        banner()
        
        # Create destination cities summary
        dest_cities_summary = ', '.join([city['name'] for city in destination_cities])
        
        print(f"Source city: {origin_city['name']}")
        print(f"Destination cities: {dest_cities_summary}")
        print("")
        print("Configure resources to send to EACH destination city:")
        print("(Enter amount to send to each city)")
        print("(Enter 0 or leave blank to NOT send that resource)")
        print("(Press '=' to restart resource configuration from beginning)")
        print("(Press ' to return to main menu)")
        print("")
        
        # Get resource amounts to send (with restart support)
        resource_config_complete = False
        while not resource_config_complete:
            resource_config = []
            restart = False
            
            for i, resource in enumerate(materials_names):
                amount = readResourceAmount(resource)
                
                if amount == 'EXIT':
                    event.set()
                    return
                
                # Check if user wants to restart
                if amount == 'RESTART':
                    print("\nRestarting resource configuration...\n")
                    restart = True
                    break
                
                # Convert None to 0 for distribute mode (simpler)
                resource_config.append(amount if amount is not None else 0)
            
            if not restart:
                resource_config_complete = True
        
        banner()
        
        # Calculate total resources needed
        total_resources_needed = [amount * len(destination_cities) for amount in resource_config]
        grand_total = sum(total_resources_needed)
        
        print(f"Configuration:")
        print(f"  Ship type: {'Freighters' if useFreighters else 'Merchant ships'}")
        print(f"  Source city: {origin_city['name']}")
        print(f"  Destination cities ({len(destination_cities)}): {dest_cities_summary}")
        print(f"")
        print(f"  Resources per destination:")
        for i, resource in enumerate(materials_names):
            if resource_config[i] > 0:
                print(f"    {resource:<10} {addThousandSeparator(resource_config[i]):>15}")
        
        print(f"")
        print(f"  Total Resources Needed:")
        print(f"    {'Resource':<10} {'Amount':>15}")
        print(f"    {'-'*10} {'-'*15}")
        for i, resource in enumerate(materials_names):
            if total_resources_needed[i] > 0:
                print(f"    {resource:<10} {addThousandSeparator(total_resources_needed[i]):>15}")
        print(f"    {'-'*10} {'-'*15}")
        print(f"    {'TOTAL':<10} {addThousandSeparator(grand_total):>15}")
        
        print("")
        
        # Ask about notifications BEFORE schedule (only if telegram is configured)
        if telegram_enabled is None:
            # User already declined telegram at the start, skip notification preferences
            notify_on_start = False
        else:
            print_module_banner("Notification Preferences")
            print("When do you want to receive Telegram notifications?")
            print("(1) Partial - When new scheduled shipment is dispatched - Total Resources to be sent")
            print("(2) All - Every Individual Shipment - can get cluttered")
            print("(3) None - No notifications")
            print("(') Back to main menu")
            notif_choice = read(min=1, max=3, digit=True, additionalValues=["'"])
            if notif_choice == "'":
                event.set()
                return
            
            # Set notification mode
            if notif_choice == 1:
                telegram_enabled = None  # No regular notifications
                notify_on_start = True  # Only start notifications
            elif notif_choice == 2:
                telegram_enabled = True  # All notifications
                notify_on_start = True
            else:  # notif_choice == 3
                telegram_enabled = None  # No notifications
                notify_on_start = False
        
        print_module_banner("Schedule Configuration")
        
        # Ask for interval
        print("How often should resources be sent (in hours)?")
        print("(0 for one-time shipment, or minimum every (1) hour for recurring)")
        print("(Press ' to return to main menu)")
        interval_hours = read(min=0, digit=True, additionalValues=["'"])
        if interval_hours == "'":
            event.set()
            return
        
        print_module_banner("Configuration Summary")
        
        print(f"Configuration summary:")
        print(f"")
        print(f"  Source city:")
        print(f"    - {origin_city['name']}")
        print(f"")
        print(f"  Destination cities ({len(destination_cities)}):")
        for city in destination_cities:
            print(f"    - {city['name']}")
        print(f"")
        print(f"  Total resources needed: {addThousandSeparator(grand_total)}")
        print(f"  Interval: {interval_hours} hour(s)" if interval_hours > 0 else "  Mode: One-time shipment")
        print("")
        print("Proceed? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return
        
        enter()
        
    except KeyboardInterrupt:
        event.set()
        return
    
    set_child_mode(session)
    event.set()
    
    info = f"\nDistribute resources from {origin_city['name']} to {len(destination_cities)} cities every {interval_hours} hour(s)\n"
    setInfoSignal(session, info)
    
    try:
        do_it_distribute(session, origin_city, destination_cities, interval_hours, resource_config, useFreighters, telegram_enabled, notify_on_start)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def do_it(session, origin_cities, destination_city, island, interval_hours, resource_config, useFreighters, send_mode, telegram_enabled, notify_on_start):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    origin_cities : list[dict]
    destination_city : dict
    island : dict
    interval_hours : int
    resource_config : list
    useFreighters : bool
    send_mode : int
    telegram_enabled : bool or None
    notify_on_start : bool
    """
    
    first_run = True
    next_run_time = datetime.datetime.now()
    total_shipments = 0
    consecutive_failures = 0  # Track consecutive lock acquisition failures
    
    while True:
        current_time = datetime.datetime.now()
        
        if current_time < next_run_time and not first_run:
            time.sleep(60)
            continue
        
        # Send start notification if enabled
        if notify_on_start:
            # Calculate total resources to be sent this cycle
            total_resources_this_cycle = [0] * len(materials_names)
            grand_total_this_cycle = 0
            
            for origin_city in origin_cities:
                html_temp = session.get(city_url + str(origin_city['id']))
                origin_city_temp = getCity(html_temp)
                
                for i, resource in enumerate(materials_names):
                    if resource_config[i] is None:
                        continue
                    
                    available = origin_city_temp['availableResources'][i]
                    
                    if send_mode == 1:
                        if resource_config[i] == 0:
                            sendable = available
                        else:
                            sendable = max(0, available - resource_config[i])
                    else:
                        if resource_config[i] == 0:
                            sendable = 0
                        else:
                            sendable = min(resource_config[i], available)
                    
                    total_resources_this_cycle[i] += sendable
                    grand_total_this_cycle += sendable
            
            # Send notification
            resources_list = []
            for i, amount in enumerate(total_resources_this_cycle):
                if amount > 0:
                    resources_list.append(f"{addThousandSeparator(amount)} {materials_names[i]}")
            
            if resources_list:
                source_cities_names = ', '.join([city['name'] for city in origin_cities])
                ship_type_name = "freighters" if useFreighters else "merchant ships"
                start_msg = f"🚢 SHIPMENT STARTING\nAccount: {session.username}\nFrom: {source_cities_names}\nTo: [{island['x']}:{island['y']}] {destination_city['name']}\nShip type: {ship_type_name}\nTotal resources: {', '.join(resources_list)}\nGrand total: {addThousandSeparator(grand_total_this_cycle)}"
                sendToBot(session, start_msg)
        
        # Get updated destination city data once per cycle
        html = session.get(city_url + str(destination_city['id']))
        destination_city = getCity(html)
        
        # Loop through each origin city
        for origin_city in origin_cities:
            # Get updated origin city data
            html = session.get(city_url + str(origin_city['id']))
            origin_city = getCity(html)
        
            # Calculate resources to send
            toSend = [0] * len(materials_names)
            total_to_send = 0
            
            for i, resource in enumerate(materials_names):
                # Skip if resource is ignored (None)
                if resource_config[i] is None:
                    toSend[i] = 0
                    continue
                
                available = origin_city['availableResources'][i]
                
                if send_mode == 1:
                    # Mode 1: Send all EXCEPT reserves (keep X, send rest)
                    if resource_config[i] == 0:
                        # Send all
                        sendable = available
                    else:
                        # Keep reserve, send excess
                        sendable = max(0, available - resource_config[i])
                else:
                    # Mode 2: Send SPECIFIC amounts (send exactly X)
                    if resource_config[i] == 0:
                        # Don't send
                        sendable = 0
                    else:
                        # Send specific amount (up to what's available)
                        sendable = min(resource_config[i], available)
                
                # Check destination space
                if destination_city.get('isOwnCity', False):
                    destination_space = destination_city['freeSpaceForResources'][i]
                    sendable = min(sendable, destination_space)
                
                toSend[i] = sendable
                total_to_send += sendable
            
            # Send resources if there's anything to send
            if total_to_send > 0:
                # Check for available ships every 2 minutes until we can send
                ship_type = 'freighters' if useFreighters else 'merchant ships'
                ships_available = False
                ship_check_start = time.time()
                
                while not ships_available:
                    # Check ship availability
                    if useFreighters:
                        available_ships = getAvailableFreighters(session)
                    else:
                        available_ships = getAvailableShips(session)
                    
                    if available_ships > 0:
                        ships_available = True
                        session.setStatus(
                            f"{origin_city['name']} -> {destination_city['name']} | Found {available_ships} {ship_type}, attempting to send..."
                        )
                    else:
                        # No ships available, wait 2 minutes and check again
                        wait_time = 120
                        elapsed = int(time.time() - ship_check_start)
                        session.setStatus(
                            f"{origin_city['name']} -> {destination_city['name']} | Waiting for {ship_type} (checked for {elapsed}s)..."
                        )
                        time.sleep(wait_time)
                
                # Try to acquire shipping lock with retries
                max_retries = 3
                retry_count = 0
                lock_acquired = False
                
                while retry_count < max_retries and not lock_acquired:
                    session.setStatus(
                        f"{origin_city['name']} -> {destination_city['name']} | Waiting for shipping lock (attempt {retry_count + 1}/{max_retries})..."
                    )
                    
                    if acquire_shipping_lock(session, use_freighters=useFreighters, timeout=300):
                        lock_acquired = True
                    else:
                        retry_count += 1
                        if retry_count < max_retries and telegram_enabled:
                            msg = f"Account: {session.username}\nFrom: {origin_city['name']}\nTo: [{island['x']}:{island['y']}] {destination_city['name']}\nProblem: Failed to acquire shipping lock on attempt {retry_count}/{max_retries}\nAction: Retrying in 1 minute..."
                            sendToBot(session, msg)
                        time.sleep(60)  # Wait 1 minute before retry
            
                if lock_acquired:
                    try:
                        route = (
                            origin_city,
                            destination_city,
                            island["id"],
                            *toSend,
                        )
                        
                        session.setStatus(
                            f"{origin_city['name']} -> {destination_city['name']} | Sending resources..."
                        )
                        
                        executeRoutes(session, [route], useFreighters)
                        total_shipments += 1
                        
                        # Reset consecutive failures on success
                        consecutive_failures = 0
                        
                        # Calculate ships used
                        ship_capacity, freighter_capacity = getShipCapacity(session)
                        capacity = freighter_capacity if useFreighters else ship_capacity
                        ships_used = (total_to_send + capacity - 1) // capacity  # Ceiling division
                        ship_type_name = "freighters" if useFreighters else "merchant ships"
                        
                        # Create summary message
                        resources_sent = []
                        for i, amount in enumerate(toSend):
                            if amount > 0:
                                resources_sent.append(f"{addThousandSeparator(amount)} {materials_names[i]}")
                        
                        if telegram_enabled:
                            msg = f"Account: {session.username}\nFrom: {origin_city['name']}\nTo: [{island['x']}:{island['y']}] {destination_city['name']}\nShips: {ships_used} {ship_type_name}\nSent: {', '.join(resources_sent)}"
                            sendToBot(session, msg)
                        
                    finally:
                        release_shipping_lock(session, use_freighters=useFreighters)
                else:
                    # Failed all retry attempts
                    consecutive_failures += 1
                    if telegram_enabled:
                        msg = f"Account: {session.username}\nFrom: {origin_city['name']}\nTo: [{island['x']}:{island['y']}] {destination_city['name']}\nProblem: Could not acquire shipping lock\nAttempts: {max_retries}\nConsecutive failures: {consecutive_failures}\nAction: Skipping this cycle"
                        sendToBot(session, msg)
                    
                    # Alert if too many consecutive failures
                    if consecutive_failures >= 3 and telegram_enabled:
                        alert_msg = f"⚠️ WARNING\nAccount: {session.username}\nFrom: {origin_city['name']}\nTo: [{island['x']}:{island['y']}] {destination_city['name']}\nProblem: {consecutive_failures} consecutive shipping failures\nPlease check for issues!"
                        sendToBot(session, alert_msg)
            else:
                if telegram_enabled:
                    msg = f"Account: {session.username}\nFrom: {origin_city['name']}\nTo: [{island['x']}:{island['y']}] {destination_city['name']}\nStatus: No resources to send (all below thresholds or no space)"
                    sendToBot(session, msg)
        
        # End of origin cities loop
        
        # Exit if one-time shipment (interval = 0)
        if interval_hours == 0:
            source_cities_names = ', '.join([city['name'] for city in origin_cities])
            session.setStatus(f"One-time shipment completed: {source_cities_names} -> {destination_city['name']}")
            return
        
        # Schedule next run for recurring shipments
        next_run_time = datetime.datetime.now() + datetime.timedelta(hours=interval_hours)
        
        # Create summary of all source cities for status
        source_cities_names = ', '.join([city['name'] for city in origin_cities])
        
        session.setStatus(
            f"{source_cities_names} -> {destination_city['name']} | Shipments: {total_shipments} | Next: {getDateTime(next_run_time.timestamp())}"
        )
        
        first_run = False
        time.sleep(60 * 60)  # Sleep for 1 hour, then check if it's time


def do_it_distribute(session, origin_city, destination_cities, interval_hours, resource_config, useFreighters, telegram_enabled, notify_on_start):
    """
    Distribute resources from one city to multiple destinations
    
    Parameters
    ----------
    session : ikabot.web.session.Session
    origin_city : dict
    destination_cities : list[dict]
    interval_hours : int
    resource_config : list
    useFreighters : bool
    telegram_enabled : bool or None
    notify_on_start : bool
    """
    
    first_run = True
    next_run_time = datetime.datetime.now()
    total_shipments = 0
    consecutive_failures = 0
    
    while True:
        current_time = datetime.datetime.now()
        
        if current_time < next_run_time and not first_run:
            time.sleep(60)
            continue
        
        # Send start notification if enabled
        if notify_on_start:
            # Calculate total resources needed
            total_resources_needed = [amount * len(destination_cities) for amount in resource_config]
            grand_total = sum(total_resources_needed)
            
            resources_list = []
            for i, amount in enumerate(total_resources_needed):
                if amount > 0:
                    resources_list.append(f"{addThousandSeparator(amount)} {materials_names[i]}")
            
            if resources_list:
                dest_names = ', '.join([city['name'] for city in destination_cities])
                ship_type_name = "freighters" if useFreighters else "merchant ships"
                start_msg = f"🚢 SHIPMENT STARTING\nAccount: {session.username}\nFrom: {origin_city['name']}\nTo: {len(destination_cities)} cities ({dest_names})\nShip type: {ship_type_name}\nTotal resources: {', '.join(resources_list)}\nGrand total: {addThousandSeparator(grand_total)}"
                sendToBot(session, start_msg)
        
        # Get updated origin city data once per cycle
        html = session.get(city_url + str(origin_city['id']))
        origin_city = getCity(html)
        
        # Get origin island data
        origin_island_id = origin_city['islandId']
        html_island = session.get(island_url + str(origin_island_id))
        origin_island = getIsland(html_island)
        
        # Loop through each destination city
        for destination_city in destination_cities:
            # Get updated destination city data
            html = session.get(city_url + str(destination_city['id']))
            destination_city = getCity(html)
            
            # Get destination island data
            dest_island_id = destination_city['islandId']
            html_dest_island = session.get(island_url + str(dest_island_id))
            dest_island = getIsland(html_dest_island)
            
            # Calculate resources to send
            toSend = [0] * len(materials_names)
            total_to_send = 0
            
            for i, resource in enumerate(materials_names):
                # Skip if not configured
                if resource_config[i] == 0:
                    toSend[i] = 0
                    continue
                
                available = origin_city['availableResources'][i]
                requested = resource_config[i]
                
                # Send up to the requested amount
                sendable = min(requested, available)
                
                # Check destination space
                if destination_city.get('isOwnCity', True):  # Assume own city in distribute mode
                    destination_space = destination_city['freeSpaceForResources'][i]
                    sendable = min(sendable, destination_space)
                
                toSend[i] = sendable
                total_to_send += sendable
            
            # Send resources if there's anything to send
            if total_to_send > 0:
                # Check for available ships
                ship_type = 'freighters' if useFreighters else 'merchant ships'
                ships_available = False
                ship_check_start = time.time()
                
                while not ships_available:
                    if useFreighters:
                        available_ships = getAvailableFreighters(session)
                    else:
                        available_ships = getAvailableShips(session)
                    
                    if available_ships > 0:
                        ships_available = True
                        session.setStatus(
                            f"{origin_city['name']} -> {destination_city['name']} | Found {available_ships} {ship_type}, attempting to send..."
                        )
                    else:
                        wait_time = 120
                        elapsed = int(time.time() - ship_check_start)
                        session.setStatus(
                            f"{origin_city['name']} -> {destination_city['name']} | Waiting for {ship_type} (checked for {elapsed}s)..."
                        )
                        time.sleep(wait_time)
                
                # Try to acquire shipping lock with retries
                max_retries = 3
                retry_count = 0
                lock_acquired = False
                
                while retry_count < max_retries and not lock_acquired:
                    session.setStatus(
                        f"{origin_city['name']} -> {destination_city['name']} | Waiting for shipping lock (attempt {retry_count + 1}/{max_retries})..."
                    )
                    
                    if acquire_shipping_lock(session, use_freighters=useFreighters, timeout=300):
                        lock_acquired = True
                    else:
                        retry_count += 1
                        if retry_count < max_retries and telegram_enabled:
                            msg = f"Account: {session.username}\nFrom: {origin_city['name']}\nTo: [{dest_island['x']}:{dest_island['y']}] {destination_city['name']}\nProblem: Failed to acquire shipping lock on attempt {retry_count}/{max_retries}\nAction: Retrying in 1 minute..."
                            sendToBot(session, msg)
                        time.sleep(60)
                
                if lock_acquired:
                    try:
                        route = (
                            origin_city,
                            destination_city,
                            dest_island["id"],
                            *toSend,
                        )
                        
                        session.setStatus(
                            f"{origin_city['name']} -> {destination_city['name']} | Sending resources..."
                        )
                        
                        executeRoutes(session, [route], useFreighters)
                        total_shipments += 1
                        
                        # Reset consecutive failures on success
                        consecutive_failures = 0
                        
                        # Calculate ships used
                        ship_capacity, freighter_capacity = getShipCapacity(session)
                        capacity = freighter_capacity if useFreighters else ship_capacity
                        ships_used = (total_to_send + capacity - 1) // capacity  # Ceiling division
                        ship_type_name = "freighters" if useFreighters else "merchant ships"
                        
                        # Create summary message
                        resources_sent = []
                        for i, amount in enumerate(toSend):
                            if amount > 0:
                                resources_sent.append(f"{addThousandSeparator(amount)} {materials_names[i]}")
                        
                        if telegram_enabled:
                            msg = f"Account: {session.username}\nFrom: {origin_city['name']}\nTo: [{dest_island['x']}:{dest_island['y']}] {destination_city['name']}\nShips: {ships_used} {ship_type_name}\nSent: {', '.join(resources_sent)}"
                            sendToBot(session, msg)
                        
                    finally:
                        release_shipping_lock(session, use_freighters=useFreighters)
                else:
                    # Failed all retry attempts
                    consecutive_failures += 1
                    if telegram_enabled:
                        msg = f"Account: {session.username}\nFrom: {origin_city['name']}\nTo: [{dest_island['x']}:{dest_island['y']}] {destination_city['name']}\nProblem: Could not acquire shipping lock\nAttempts: {max_retries}\nConsecutive failures: {consecutive_failures}\nAction: Skipping this destination"
                        sendToBot(session, msg)
                    
                    if consecutive_failures >= 3 and telegram_enabled:
                        alert_msg = f"⚠️ WARNING\nAccount: {session.username}\nFrom: {origin_city['name']}\nTo: [{dest_island['x']}:{dest_island['y']}] {destination_city['name']}\nProblem: {consecutive_failures} consecutive shipping failures\nPlease check for issues!"
                        sendToBot(session, alert_msg)
            else:
                if telegram_enabled:
                    msg = f"Account: {session.username}\nFrom: {origin_city['name']}\nTo: [{dest_island['x']}:{dest_island['y']}] {destination_city['name']}\nStatus: No resources to send (insufficient or no space)"
                    sendToBot(session, msg)
        
        # End of destination cities loop
        
        # Exit if one-time shipment
        if interval_hours == 0:
            dest_names = ', '.join([city['name'] for city in destination_cities])
            session.setStatus(f"One-time distribution completed: {origin_city['name']} -> {dest_names}")
            return
        
        # Schedule next run
        next_run_time = datetime.datetime.now() + datetime.timedelta(hours=interval_hours)
        
        dest_names = ', '.join([city['name'] for city in destination_cities])
        session.setStatus(
            f"{origin_city['name']} -> {len(destination_cities)} cities | Shipments: {total_shipments} | Next: {getDateTime(next_run_time.timestamp())}"
        )
        
        first_run = False
        time.sleep(60 * 60)  # Sleep for 1 hour, then check if it's time


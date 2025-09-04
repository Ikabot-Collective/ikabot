#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from ikabot.config import *
from ikabot.helpers.pedirInfo import *

# import json
# import re
# from ikabot.helpers.getJson import *
# from ikabot.helpers.gui import *
# from ikabot.helpers.resources import *
# from ikabot.helpers.varios import *


def modifyProduction(session, event, stdin_fd, predetermined_input):
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
        mod_msg = "In which cities do you want to modify production?"
        city_ids, _ = ignoreCities(session, msg=mod_msg)
        
        cities_to_process = {}
        #print("DEBUG: Fetching detailed information for selected cities...")
        for city_id in city_ids:
            html = session.get(city_url + city_id)
            city = getCity(html)
            if city['islandId'] not in cities_to_process:
                cities_to_process[city['islandId']] = {'island': getIsland(session.get(island_url + city['islandId'])), 'cities': []}
            cities_to_process[city['islandId']]['cities'].append(city)
            #print(f"DEBUG: Got city data for {city_id}")
        

        print("You want to modify the number of workers in Wood (1), Tradegood (2) or Both (3)?")
        res_choice = read(min=1, max=3)
        resource_types_to_modify = []
        if res_choice == 1:
            resource_types_to_modify.append("resource")
        elif res_choice == 2:
            resource_types_to_modify.append("tradegood")
        elif res_choice == 3:
            resource_types_to_modify.extend(["resource", "tradegood"])
            
            
        print("What % of production do you want to use? (Default 100%)")
        percentageWorkers = read(min=0, max=100, default=100)
        if percentageWorkers == 100:
            print("Would you like to use overcharge? (y/N)")
            overcharge = read(values=["y", "Y", "n", "N", ""])
            if overcharge.lower() == "y":
                use_overcharge = True
            else:
                use_overcharge = False
        else:
            use_overcharge = False
            
        banner()
        # loop through each selected city
        current_city_id_for_request = getCity(session.get())['id']
        # Loop through islands first
        for islandId, island_data in cities_to_process.items():
            island = island_data['island']
            resource_name = tradegoods_names[0]
            tradegood_name = tradegoods_names[int(island["tipo"])]
            #print(f"DEBUG: Visited island {islandId}")

            # Then loop through cities on that island
            for city in island_data['cities']:
                # Change the session context to the current city
                session.post(params={
                    'action': 'header', 'function': 'changeCurrentCity',
                    'actionRequest': actionRequest, 'cityId': city['id'],
                    'oldView': 'city', 'backgroundView': 'city',
                    'currentCityId': current_city_id_for_request, 'ajax': '1'
                })
                # Update the current city ID for the next request
                current_city_id_for_request = city['id']
                #print(f"DEBUG: session.post was made, current city is {city['id']} and island is {islandId}")

                # Loop through only the resource types the user chose to modify
                for resource_type in resource_types_to_modify:
                    # Fetch data, calculate, and set workers in one sequence
                    
                    # Fetch data for the current resource type
                    url = f"view={resource_type}&type={resource_type}&islandId={islandId}&cityId={city['id']}&backgroundView=island&currentIslandId={islandId}&actionRequest={actionRequest}&ajax=1"
                    resp = session.post(url)
                    resp_json = json.loads(resp, strict=False)
                    
                    template_data = resp_json[2][1]
                    slider_data = template_data['js_ResourceSlider']['slider']
                    max_normal = slider_data['max_value']
                    total_max = slider_data['max_value'] + slider_data['overcharge']
                    #print(f"DEBUG: session.post was made, current city is {city['id']}, current island is {islandId}\nresource type is {resource_type}, max_normal is {max_normal} and total_max is {total_max}")
                    
                    # Calculate finalWorkers using the data we just fetched
                    if percentageWorkers == 100:
                        finalWorkers = total_max if use_overcharge else max_normal
                    else:
                        finalWorkers = int(max_normal / 100 * percentageWorkers)
                    
                    # Set the workers
                    session.post(params={
                        "islandId": islandId, "cityId": city["id"],
                        "type": resource_type, "screen": resource_type,
                        "action": "IslandScreen", "function": "workerPlan",
                        "rw": finalWorkers, "templateView": resource_type,
                        "actionRequest": actionRequest, "ajax": "1"
                    })
                    
                    selected_good_name = resource_name if resource_type == "resource" else tradegood_name
                    print(f"{finalWorkers} workers set for {selected_good_name} in {city['name']}.")
                
        print("\nAll productions have been set!")
        enter()
        event.set()
        
    except KeyboardInterrupt:
        event.set()
        return 
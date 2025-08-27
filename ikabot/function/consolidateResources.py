#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import traceback
import datetime
import time

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import banner
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import executeRoutes
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.resources import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import addThousandSeparator
from ikabot.helpers.varios import getDateTime

def consolidateResources(session, event, stdin_fd, predetermined_input):
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

        citiesIds = getIdsOfCities(session)
        if len(citiesIds) == 0:
            event.set()
            return

        if len(citiesIds) == 1:
            print('You need at least two cities to consolidate resources.')
            event.set()
            return

        banner()
        source_msg = 'Select source cities to send resources from:'
        sourceCities, sourceCitiesDict = ignoreCities(session, msg=source_msg)
        
        if sourceCities is None:
            event.set()
            return

        banner()
        print('Select destination cities to receive resources:')
        destinationCity = chooseCity(session)

        if destinationCity is None:
            event.set()
            return
        
        destination_id_str = str(destinationCity['id'])
        if destination_id_str in sourceCities:
            sourceCities.remove(destination_id_str)
            del sourceCitiesDict[destination_id_str]

        banner()
        print('Define resource limits to keep:')
    
        limits = []
        
        for i, resource in enumerate(materials_names):
            prompt = 'Enter maximum {} to keep (skip to keep everything): '.format(resource)
            resourceLimit = read(msg=prompt, min=-1, default=-1)
            limits.append(resourceLimit)
        
        banner()
        print('Define how often to execute the process in hours (min - 1 hour):')
        intervalInHours = read(min=1, default=1)

        banner()
        print(('The process will transfer everything above specified limits:'))
        for i, resource in enumerate(materials_names):
            if limits[i] == -1:
                print(('- Keep all {}').format(resource))
            else:
                print(('- Keep up to {} {} and send excess').format(addThousandSeparator(limits[i]), resource))
        
        source_city_names_str = ', '.join([city['name'] for city in sourceCitiesDict.values()])
        print(('\nFrom {} to {} every {} hours').format(
            source_city_names_str, 
            destinationCity['name'], 
            intervalInHours,
        ))

        print("\nProceed? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return

        enter()

    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()  # this is where we give back control to main process

    info = 'Consolidate resources from {} to {} every {:d} hours'.format(source_city_names_str, destinationCity['name'], intervalInHours)
    setInfoSignal(session, info)

    nextExecutionTime = datetime.datetime.now() + datetime.timedelta(hours=intervalInHours)

    session.setStatus(
        f" {source_city_names_str} -> {destinationCity['name']} | Next at {getDateTime(nextExecutionTime.timestamp())}"
    )

    try:
        do_it(session, limits, sourceCities, destinationCity['id'], intervalInHours)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def do_it(session, limits, sourceCityIds, destinationCityId, intervalInHours):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    limits : array
    sourceCityIds : list[str]
    destinationCityId : int
    intervalInHours : int
    """

    firstRun = True
    nextRunTime = datetime.datetime.now()
    total_amount_sent = 0

    while True:
        currentTime = datetime.datetime.now()
        loop_amount_sent = 0
        if currentTime < nextRunTime and not firstRun:
            time.sleep(60)
            continue
            
        # Loop through each source city ID in the provided list
        for sourceCityId in sourceCityIds:
            try:
                sourceCity = getCity(session.get(city_url + str(sourceCityId)))
                destinationCity = getCity(session.get(city_url + str(destinationCityId)))
            except Exception as e:
                print(f"Failed to get data for source city ID {sourceCityId}: {e}")
                continue # Skip to the next city if one fails

            toSend = [0] * len(materials_names)
            totalToSend = 0

            session.setStatus(
                f"{sourceCity['name']} -> {destinationCity['name']}| Processing..."
            )

            for i, resource in enumerate(materials_names):
                limit = limits[i]
                
                sourceAmount = sourceCity['availableResources'][i]
                destinationSpace = destinationCity['freeSpaceForResources'][i]

                if limit == -1 or limit < 0:  # Handle any negative number as "keep all"
                    toSend[i] = 0
                else:
                    excess = max(0, sourceAmount - limit)
                    sendable = min(excess, destinationSpace)
                    toSend[i] = sendable
                    totalToSend += sendable

            if totalToSend != 0:
                route = (
                    sourceCity,
                    destinationCity,
                    destinationCity["islandId"],
                    *toSend,
                )

                executeRoutes(session, [route], useFreighters=False)
                loop_amount_sent += totalToSend
                total_amount_sent += totalToSend

        nextRunTime = datetime.datetime.now() + datetime.timedelta(hours=intervalInHours)
        
        # Get the name of each source city by its ID for the final status message
        source_city_names = [getCity(session.get(city_url + str(city_id)))['name'] for city_id in sourceCityIds]
        source_city_names_str = ', '.join(source_city_names)
        # Get the destination city's name for the status message
        destinationCityName = getCity(session.get(city_url + str(destinationCityId)))['name']

        session.setStatus(
            f"Sent {addThousandSeparator(loop_amount_sent)} resources from {source_city_names_str} -> {destinationCity['name']} | Total sent: {addThousandSeparator(total_amount_sent)} | Next shipment at {getDateTime(nextRunTime.timestamp())}"
        )

        firstRun = False

        time.sleep(60 * 60)

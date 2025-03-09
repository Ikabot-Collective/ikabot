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
        print('Select source cities to send resources from:')
        sourceCity = chooseCity(session)
        
        if sourceCity is None:
            event.set()
            return

        banner()
        print('Select destination cities to receive resources:')
        destinationCity = chooseCity(session)

        if destinationCity is None:
            event.set()
            return
        
        if sourceCity["id"] == destinationCity["id"]:
            banner()
            print("The city of origin and the destination city cannot be the same")
            enter()
            event.set()
            return

        banner()
        print(('Define resource limits to keep in {}:').format(sourceCity['name']))
    
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
        

        print(('\nFrom {} to {} every {} hours').format(
            sourceCity['name'], 
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

    info = 'Consolidate resources from {} to {} every {:d} hours'.format(sourceCity['name'], destinationCity['name'], intervalInHours)
    setInfoSignal(session, info)

    nextExecutionTime = datetime.datetime.now() + datetime.timedelta(hours=intervalInHours)

    session.setStatus(
        f" {sourceCity['name']} -> {destinationCity['name']} | Next at {getDateTime(nextExecutionTime.timestamp())}"
    )

    try:
        do_it(session, limits, sourceCity['id'], destinationCity['id'], intervalInHours)
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def do_it(session, limits, sourceCityId, destinationCityId, intervalInHours):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    limits : array
    sourceCityId : int
    destinationCityId : int
    intervalInHours : int
    """

    sourceCity = getCity(session.get(city_url + str(sourceCityId)))
    destinationCity = getCity(session.get(city_url + str(destinationCityId)))

    hasConsolidated = {}
    routes = []  # Store all routes for batch execution
    lastResetTime = datetime.datetime.now()

    while True:
        currentTime = datetime.datetime.now()
        timeElapsed = (currentTime - lastResetTime).total_seconds()
        if timeElapsed >= intervalInHours * 60 * 60:  
            hasConsolidated.clear()
            lastResetTime = currentTime  # Update the last time reseted the list
        else:
            time.sleep(60 * 60)

        try:
            sourceCity = getCity(session.get(city_url + str(sourceCityId)))
            destinationCity = getCity(session.get(city_url + str(destinationCityId)))
        except Exception as e:
            logger.error(f"Failed to get city data: {e}")
            time.sleep(300)  # Wait 5 minutes before retrying
            continue

        toSend = {}
        totalToSend = 0

        session.setStatus(
            f"{sourceCity['name']} -> {destinationCity['name']}| Processing..."
        )

        for i, resource in enumerate(materials_names):
            resourceKey = resource.lower()
            limit = limits[i]
            
            sourceAmount = sourceCity['availableResources'][i]
            destinationSpace = destinationCity['freeSpaceForResources'][i]

            if limit == -1 or limit < 0:  # Handle any negative number as "keep all"
                toSend[resourceKey] = 0
            else:
                excess = max(0, sourceAmount - limit)
                sendable = min(excess, destinationSpace)
                toSend[resourceKey] = sendable
                totalToSend += sendable

        if totalToSend == 0:
            sendToBot(session, "No excess resources to send from {}. Will check again in {} hours.".format(
                sourceCity['name'], 
                intervalInHours
            ))

            nextExecutionTime = lastResetTime + datetime.timedelta(hours=intervalInHours)
            session.setStatus(
                f" {sourceCity['name']} -> {destinationCity['name']} | Next at {getDateTime(nextExecutionTime.timestamp())}"
            )

            time.sleep(intervalInHours * 60 * 60)
            continue

        routes.append((
            sourceCity,
            destinationCity,
            destinationCity["islandId"],
            toSend.get("wood", 0),
            toSend.get("wine", 0),
            toSend.get("marble", 0),
            toSend.get("crystal", 0),
            toSend.get("sulfur", 0),
        ))

        if routes:
            executeRoutes(session, routes, useFreighters=False)

            resourceMessage = ", ".join([f"{amt} {res}" for res, amt in toSend.items() if amt > 0])
            sendToBot(session, f"Sent {resourceMessage} from {sourceCity['name']} to {destinationCity['name']}")

            routes.clear()

            nextExecutionTime = lastResetTime + datetime.timedelta(hours=intervalInHours)
            session.setStatus(
                f" {sourceCity['name']} -> {destinationCity['name']} | Next at {getDateTime(nextExecutionTime.timestamp())}"
            )

        time.sleep(60 * 60)

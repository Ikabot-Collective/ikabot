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

        print("In what city do you want modify your production?")
        city = chooseCity(session)
        banner()

        islandId = city["islandId"]
        html = session.get(island_url + islandId)
        island = getIsland(html)

        island_type = island["tipo"]
        resource_name = tradegoods_names[0]
        tradegood_name = tradegoods_names[int(island_type)]

        # get resource information
        url = "view=resource&type=resource&islandId={0}&backgroundView=island&currentIslandId={0}&actionRequest={1}&ajax=1".format(
            islandId, actionRequest
        )
        resp = session.post(url)
        resp = json.loads(resp, strict=False)
        
        citizens, workers = re.findall(
            r'<span class="scroll_view" (.*?)</span>', resp[1][1][1]
        )
        
        citizens = citizens.replace(",", "").replace(".", "").replace('id="valueCitizens">',"")
        citizens = int(citizens)
        workers = workers.replace(",", "").replace(".", "").replace('id="valueWorkers">',"")
        workers = int(workers)
                
        msg = "You want to modify the number of workers in {} (1) or in {} (2)?:".format(
                resource_name, tradegood_name
            )
        
        whereToModProd = read(msg=msg, min=1, max=2)
        whereToModProd = "resource" if whereToModProd == 1 else "tradegood"
        
        msg = "What % of all your citizens you want to put in the {} (0: None -> 100: Max; Default 100%)?:".format(
                resource_name if whereToModProd == "resource" else tradegood_name, citizens+workers
            )
        
        finalWorkers = read(msg=msg, min=0, max=100, default=100)        
        finalWorkers =  citizens+workers if finalWorkers == 100 else int(finalWorkers/100 * (citizens+workers))
         
        print("")
        
        # print("To set: {} workers in {}[{}]".format(finalWorkers, islandId, city["id"]))
        
        session.post(
            params={
                "islandId": islandId,
                "cityId": city["id"],
                "type": whereToModProd,
                "screen": whereToModProd,
                "action": "IslandScreen",
                "function": "workerPlan",
                "rw": int(finalWorkers),
                "templateView": whereToModProd,
                "actionRequest": actionRequest,
                "ajax": "1"
            }
        )
        
        print("You've set {} worker(s) in the {}.".format(
            finalWorkers, resource_name if whereToModProd == "resource" else tradegood_name
        ))

        enter()
        event.set()
        
        return
    except KeyboardInterrupt:
        event.set()
        return

#! /usr/bin/env python3
# -*- coding: utf-8 -*-


import sys
import time
import traceback

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.gui import bcolors, enter
from ikabot.helpers.pedirInfo import chooseCity, getIdsOfCities
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import getDateTime, timeStringToSec, wait


earliest_wakeup_time = 24 * 60 * 60
wine_city = wood_city = luxury_city = favour_tasks = None


def loginDaily(session, event, stdin_fd, predetermined_input):
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
        global wine_city
        print("Choose the city where the daily login bonus wine will be sent:")
        wine_city = chooseCity(session)
        print("Do you want to automatically activate the cinetheatre bonus? (Y|N)")
        choice = read(values=["y", "Y", "n", "N"])
        if choice in ["y", "Y"]:

            # choose city for wood
            print("Choose the city where the wood bonus will be activated:")
            wood_city = chooseCity(session)

            # choose city for luxury resource
            print("Choose the city where the luxury resource bonus will be activated:")
            luxury_city = chooseCity(session)
        print("Do you want to collect the favour automatically? (Y|N)")
        choice = read(values=["y", "Y", "n", "N"])
        if choice in ["y", "Y"]:
            favour_tasks = [t for t in tasks]

            def modify_tasks():
                banner()
                print(
                    "Choose which daily tasks will be done/collected by Ikabot automatically."
                )
                print(
                    f"Tasks in {bcolors.BLUE}blue{bcolors.ENDC} WILL be done automatically, tasks in {bcolors.STONE}grey{bcolors.ENDC} WILL NOT be done."
                )
                print("Press [ENTER] or type in [Y] to confirm selection")
                for i, task in enumerate(tasks):
                    if task in favour_tasks:
                        print(i + 1, ") ", bcolors.BLUE, task, bcolors.ENDC)
                    else:
                        print(i + 1, ") ", bcolors.STONE, task, bcolors.ENDC)
                choice = read(
                    min=1,
                    max=len(tasks),
                    empty=True,
                    digit=True,
                    additionalValues=["y", "Y"],
                )
                if not choice or (not choice.isdigit() and choice.lower() == "y"):
                    return
                choice -= 1
                if list(tasks)[choice] in favour_tasks:
                    favour_tasks.remove(list(tasks)[choice])
                else:
                    favour_tasks.append(list(tasks)[choice])
                return modify_tasks()

            modify_tasks()

        print("I will do the thing.")
        enter()
    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()

    info = "\nI enter every day\n"
    setInfoSignal(session, info)
    try:
        do_it(
            session,
            wine_city=wine_city,
            wood_city=wood_city,
            luxury_city=luxury_city,
            favour_tasks=favour_tasks,
        )
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)
    finally:
        session.logout()


def do_it(session, wine_city, wood_city, luxury_city, favour_tasks):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    """
    message_sent = False
    while True:
        (ids, cities) = getIdsOfCities(session)
        global earliest_wakeup_time
        earliest_wakeup_time = 24 * 60 * 60
        # collect daily bonus wine
        html = session.post(city_url + str(wine_city["id"]))
        url = "action=AvatarAction&function=giveDailyActivityBonus&dailyActivityBonusCitySelect={0}&startPageShown=1&detectedDevice=1&autoLogin=on&cityId={0}&activeTab=multiTab2&backgroundView=city&currentCityId={0}&actionRequest={1}&ajax=1".format(
            wine_city["id"], actionRequest
        )
        session.post(url)

        def get_remaining_time_cinetheatre(features):
            ewt = 999999999
            for i, feature in enumerate(["Resource", "Tradegood", "Favour"]):
                if features[i] and f"js_nextPossible{feature}" in features[i]:
                    remaining_time_str = re.search(
                        rf'js_nextPossible{feature}\\">([\S\s]*?)<', features[i]
                    )
                    assert (
                        remaining_time_str
                    ), f"Could not get remaining time for {feature} cultural feature"
                    remaining_time_str = remaining_time_str.group(1).strip()
                    sec_to_wait = (
                        timeStringToSec(remaining_time_str) + 60
                    )  # add 60s because of rounding errors
                    ewt = sec_to_wait if sec_to_wait < ewt else ewt
            return ewt

        # collect wood cultural bonus
        if wood_city:
            html = session.post(city_url + str(wood_city["id"]))
            html = session.post(
                f"view=cinema&visit=1&currentCityId={wood_city['id']}&backgroundView=city&actionRequest={actionRequest}&ajax=1"
            )
            features = (
                html.split('id=\\"VideoRewards\\"')[1].split("ul>")[0].split("li>")
            )
            features = [f for f in features if "form" in f or "js_nextPossible" in f]
            if "js_nextPossibleResource" in features[0]:
                earliest_wakeup_time = (
                    get_remaining_time_cinetheatre(features)
                    if get_remaining_time_cinetheatre(features) < earliest_wakeup_time
                    else earliest_wakeup_time
                )
            else:
                videoId = re.search(
                    r'name=\\"videoId\\"\s*value=\\"(\d+)\\"', features[0]
                )
                assert videoId, "Could not find a match for videoId in html"
                videoId = videoId.group(1)
                session.post(
                    f"view=noViewChange&action=AdVideoRewardAction&function=requestBonus&bonusId=51&videoId={str(videoId)}&backgroundView=city&currentCityId={wood_city['id']}&templateView=cinema&actionRequest={actionRequest}&ajax=1"
                )
                session.setStatus("Waiting 55s to watch video for wood bonus")
                wait(55)
                session.post(
                    f"view=noViewChange&action=AdVideoRewardAction&function=watchVideo&videoId={str(videoId)}&backgroundView=city&currentCityId={wood_city['id']}&templateView=cinema&actionRequest={actionRequest}&ajax=1"
                )

        wait(1)

        # collect luxury good cultural bonus
        if luxury_city:
            html = session.post(city_url + str(luxury_city["id"]))
            html = session.post(
                f"view=cinema&visit=1&currentCityId={luxury_city['id']}&backgroundView=city&actionRequest={actionRequest}&ajax=1"
            )
            features = (
                html.split('id=\\"VideoRewards\\"')[1].split("ul>")[0].split("li>")
            )
            features = [f for f in features if "form" in f or "js_nextPossible" in f]
            if "js_nextPossibleTradegood" in features[1]:
                earliest_wakeup_time = (
                    get_remaining_time_cinetheatre(features)
                    if get_remaining_time_cinetheatre(features) < earliest_wakeup_time
                    else earliest_wakeup_time
                )
            else:
                videoId = re.search(
                    r'name=\\"videoId\\"\s*value=\\"(\d+)\\"', features[1]
                )
                assert videoId, "Could not find a match for videoId in html"
                videoId = videoId.group(1)
                session.post(
                    f"view=noViewChange&action=AdVideoRewardAction&function=requestBonus&bonusId=52&videoId={str(videoId)}&backgroundView=city&currentCityId={luxury_city['id']}&templateView=cinema&actionRequest={actionRequest}&ajax=1"
                )
                session.setStatus("Waiting 55s to watch video for luxury good bonus")
                wait(55)
                session.post(
                    f"view=noViewChange&action=AdVideoRewardAction&function=watchVideo&videoId={str(videoId)}&backgroundView=city&currentCityId={luxury_city['id']}&templateView=cinema&actionRequest={actionRequest}&ajax=1"
                )

        wait(1)

        # collect favour cultural bonus
        if wood_city:
            favour_cinetheater_city = wood_city
        if luxury_city:
            favour_cinetheater_city = luxury_city
        if favour_cinetheater_city:
            html = session.post(city_url + str(favour_cinetheater_city["id"]))
            html = session.post(
                f"view=cinema&visit=1&currentCityId={favour_cinetheater_city['id']}&backgroundView=city&actionRequest={actionRequest}&ajax=1"
            )
            features = (
                html.split('id=\\"VideoRewards\\"')[1].split("ul>")[0].split("li>")
            )
            features = [f for f in features if "form" in f or "js_nextPossible" in f]
            if "js_nextPossibleFavour" in features[2]:
                earliest_wakeup_time = (
                    get_remaining_time_cinetheatre(features)
                    if get_remaining_time_cinetheatre(features) < earliest_wakeup_time
                    else earliest_wakeup_time
                )
            else:
                videoId = re.search(
                    r'name=\\"videoId\\"\s*value=\\"(\d+)\\"', features[2]
                )
                assert videoId, "Could not find a match for videoId in html"
                videoId = videoId.group(1)
                session.post(
                    f"view=noViewChange&action=AdVideoRewardAction&function=requestBonus&bonusId=53&videoId={str(videoId)}&backgroundView=city&currentCityId={favour_cinetheater_city['id']}&templateView=cinema&actionRequest={actionRequest}&ajax=1"
                )
                session.setStatus(
                    "Waiting 55s to watch video for favour cultural bonus"
                )
                wait(55)
                session.post(
                    f"view=noViewChange&action=AdVideoRewardAction&function=watchVideo&videoId={str(videoId)}&backgroundView=city&currentCityId={favour_cinetheater_city['id']}&templateView=cinema&actionRequest={actionRequest}&ajax=1"
                )

        # get waiting times for all three cinetheatre features.

        wait(1)

        if wood_city or luxury_city or favour_cinetheater_city:
            html = session.post(city_url + str(wine_city["id"]))
            html = session.post(
                f"view=cinema&visit=1&currentCityId={wine_city['id']}&backgroundView=city&actionRequest={actionRequest}&ajax=1"
            )
            features = (
                html.split('id=\\"VideoRewards\\"')[1].split("ul>")[0].split("li>")
            )
            features = [f for f in features if "form" in f or "js_nextPossible" in f]
            earliest_wakeup_time = (
                get_remaining_time_cinetheatre(features)
                if get_remaining_time_cinetheatre(features) < earliest_wakeup_time
                else earliest_wakeup_time
            )

        wait(1)

        # do favour tasks in wine city
        for task in favour_tasks:
            html = session.post(city_url + str(wine_city["id"]))
            html = session.post(
                f"view=dailyTasks&backgroundView=city&currentCityId={wine_city['id']}&actionRequest={actionRequest}&ajax=1"
            )
            # check if favour is full (2500)
            match = re.search(r"currentFavor([\S\s]*?)(\d+)\s*<", html)
            assert match, "Can not obtain current favour amount"
            if match.group(2) == "2500":
                # send notification we are full on favour
                if not message_sent:
                    sendToBot(session, "Favour was not collected as you are full on it")
                    message_sent = (
                        True  # we don't want to spam the message, only once is enough
                    )
                break
            matches = re.findall("<tr([\S\s]*?)tr>", html)
            rows = [
                matches[1],
                matches[2],
                matches[4],
                matches[5],
                matches[7],
                matches[8],
                matches[10],
                matches[11],
            ]
            tasks[task](session, rows)
            match = re.search(
                r'"dailyTasksCountdown":{"countdown":{"enddate":(\d+),"currentdate":(\d+),"timeout_ajax',
                html,
            )
            assert match, "Can not get remaning daily tasks time"
            sec_remaining = (int(match.group(1)) - int(match.group(2))) - 600
            earliest_wakeup_time = (
                sec_remaining
                if sec_remaining < earliest_wakeup_time
                else earliest_wakeup_time
            )

        # find capital and get ambro bonus from fountain if it's active
        for id in ids:
            html = session.post(city_url + str(id))
            if 'class="fountain' in html:  # is capital
                if 'class="fountain_active' in html:  # foutain is active
                    url = "action=AmbrosiaFountainActions&function=collect&backgroundView=city&currentCityId={0}&templateView=ambrosiaFountain&actionRequest={1}&ajax=1".format(
                        id, actionRequest
                    )
                    session.post(url)
                break
            wait(1)
        earliest_wakeup_time = abs(
            earliest_wakeup_time
        )  # funnily enough, it's possible to have the earliest wakeup time be a negative number, this happens if there is less than 10 minutes remaning until tasks reset
        session.setStatus(
            f"Last activity @{getDateTime()}, next activity @{getDateTime(time.time()+earliest_wakeup_time)}"
        )
        wait(earliest_wakeup_time, 20)


def is_collectable(row):
    progress_left = (
        re.search(r"smallright progress details([\S\s]*?)>([\S\s]*?)<", row)
        .group(2)
        .strip()
        .replace(",", "")
    )
    progress_right = (
        re.search(r"left small progress details([\S\s]*?)>([\S\s]*?)<", row)
        .group(2)
        .strip()
        .replace(",", "")
    )
    return "textLineThrough" not in row and progress_left == progress_right


def collect_resource_favour(session, table):
    # literally just collect the first two tasks if they're done
    global wine_city
    passive1 = table[0]
    passive2 = table[1]

    if is_collectable(passive1):
        taskId = re.search(r'taskId=([\S\s]*?)\\"', passive1).group(1)
        session.post(
            f"action=CollectDailyTasksFavor&taskId={taskId}&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
        )
        wait(1)

    if is_collectable(passive2):
        taskId = re.search(r'taskId=([\S\s]*?)\\"', passive2).group(1)
        session.post(
            f"action=CollectDailyTasksFavor&taskId={taskId}&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
        )
        wait(1)


def look(session, table):
    # collect if collectable, otherwise look at specified view then collect
    global earliest_wakeup_time, wine_city
    for r in table:
        if "task_amount_28" in r:  # visit shop
            if is_collectable(r):
                session.post(
                    f"action=CollectDailyTasksFavor&taskId=28&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)
            else:
                session.post(
                    f"view=premium&linkType=2&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)
                session.post(
                    f"action=CollectDailyTasksFavor&taskId=28&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)

        if "task_amount_27" in r:  # open inventory
            if is_collectable(r):
                session.post(
                    f"action=CollectDailyTasksFavor&taskId=27&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)
            else:
                session.post(
                    f"view=inventory&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)
                session.post(
                    f"action=CollectDailyTasksFavor&taskId=27&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)

        if "task_amount_26" in r:  # look at highscore
            if is_collectable(r):
                session.post(
                    f"action=CollectDailyTasksFavor&taskId=26&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)
            else:
                session.post(
                    f"view=highscore&showMe=1&backgroundView=city&currentCityId={wine_city['id']}&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)
                session.post(
                    f"action=CollectDailyTasksFavor&taskId=26&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)


def capture_runs(session, table):
    # divide number of point by 115, take top integer, invoke autopirate for that many runs, collect bonus
    pass


def donate_wood(session, table):
    # find city with most wood and donate number of it to lux resource or wood production (randomly chosen), collect bonus
    pass


def stay_online_30_mins(session, table):
    # collect if possible, otherwise earliest wake time is 31 mins from now, then it will be collected in the next pass
    global earliest_wakeup_time, wine_city
    for r in table:
        if "task_amount_23" in r:  # stay online for 30 mins
            if is_collectable(r):
                session.post(
                    f"action=CollectDailyTasksFavor&taskId=23&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
                )
                wait(1)
            else:
                earliest_wakeup_time = (
                    31 * 60 if 31 * 60 < earliest_wakeup_time else earliest_wakeup_time
                )


def complete_tasks(session, table):
    # collect any still collectable tasks, this one should always run last
    global wine_city
    for row in table:
        if is_collectable(row):
            taskId = re.search(r'taskId=([\S\s]*?)\\"', row).group(1)
            session.post(
                f"action=CollectDailyTasksFavor&taskId={taskId}&ajax=1&backgroundView=city&currentCityId={wine_city['id']}&templateView=dailyTasks&actionRequest={actionRequest}&ajax=1"
            )
            wait(1)


tasks = {
    "Collect resource favour": collect_resource_favour,
    "Look at hightscore/shop/inventory": look,
    "Stay online for 30 mins": stay_online_30_mins,
    #'Conduct capture runs': capture_runs,
    #'Donate wood': donate_wood,
    "Complete 2/all tasks": complete_tasks,  # must be last
}

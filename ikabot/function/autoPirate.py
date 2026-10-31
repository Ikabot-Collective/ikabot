#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import json
import re
import sys
import time
import traceback

import requests

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import run, set_child_mode, updateProcessList
from ikabot.helpers.varios import timeStringToSec, wait
from ikabot.helpers.apiComm import getPiratesCaptchaSolution

try:
    from ikabot.helpers.piratesDecaptcha import get_captcha_string
    LOCAL_DECAPTCHA = True
except Exception:
    LOCAL_DECAPTCHA = False

try:
    from ikabot.helpers.logging import getLogger
    _logger = getLogger(__name__)
except Exception:
    import logging
    _logger = logging.getLogger(__name__)


from ikabot.helpers.decorators import configurator, task
from ikabot.helpers.taskConfig import asBool, asId, asInt

def isHourInRange(hour, start, end):
    """Inclusive hour range, supports ranges that cross midnight (e.g. 19 till 9)."""
    if start <= end:
        return start <= hour <= end
    return hour >= start or hour <= end


def getScheduledMission(dayStart, dayEnd, nightStart, nightEnd, dayChoice, nightChoice):
    """Returns the mission for the current hour, or None if it is outside both ranges."""
    hour = time.localtime().tm_hour
    if isHourInRange(hour, dayStart, dayEnd):
        return dayChoice
    if isHourInRange(hour, nightStart, nightEnd):
        return nightChoice
    return None


def getSecondsUntilNextRange(dayStart, nightStart):
    now = time.localtime()
    hours = min((start - now.tm_hour) % 24 or 24 for start in (dayStart, nightStart))
    return hours * 3600 - now.tm_min * 60 - now.tm_sec


def extract_captcha_image(html):
    """Extract the pirates captcha PNG bytes from the capture response.

    The captcha image is now embedded by the game as a base64 data URI
    (js_captchaImage.src) inside the JSON response of the capture request,
    instead of being served on a separate createCaptcha endpoint.
    """
    if not isinstance(html, str):
        return None

    # Prefer parsing the JSON response, which unescapes everything for us.
    try:
        data = json.loads(html)
    except Exception:
        data = None
    if isinstance(data, list):
        for command, payload in data:
            if command == "updateTemplateData" and isinstance(payload, dict):
                image = payload.get("js_captchaImage")
                if isinstance(image, dict) and isinstance(image.get("src"), str):
                    match = re.search(
                        r"data:image/png;base64,([A-Za-z0-9+/=]+)", image["src"]
                    )
                    if match:
                        return base64.b64decode(match.group(1))

    # Fallback: parse the base64 straight out of the raw (JSON-escaped) html.
    match = re.search(r"base64,([A-Za-z0-9+/=\\\\]+)", html)
    if match:
        b64 = match.group(1).replace("\\/", "/").replace("\n", "").replace("\r", "")
        try:
            return base64.b64decode(b64)
        except Exception:
            return None
    return None

def prepare_autoPirate(
    session,
    pirateCount,
    pirateSchedule=False,
    pirateMissionChoice=None,
    pirateMissionDayChoice=None,
    pirateMissionNightChoice=None,
    dayStart=10,
    dayEnd=18,
    nightStart=19,
    nightEnd=9,
    autoConvert="n",
    convertPerMission=0,
    maxRandomWaitingTime=0,
    piracyCities=None,
):
    """Checks the config of an autoPirate task started from the CLI
    Parameters
    ----------
    session : ikabot.web.session.Session
    pirateCount : int
        number of missions
    pirateSchedule : bool
        True does pirateMissionDayChoice between dayStart and dayEnd and
        pirateMissionNightChoice between nightStart and nightEnd
    pirateMissionChoice : int
        mission 1 (2m 30s) to 9 (16h), used without a schedule
    autoConvert : bool or str
    convertPerMission : int or "all"
    maxRandomWaitingTime : int
        extra random seconds between missions
    piracyCities : list
        only the first city's id is used, as the city to try first

    Returns
    -------
    config : dict
    """
    pirateSchedule = asBool(pirateSchedule, "pirateSchedule")
    config = {
        "pirateCount": asInt(pirateCount, "pirateCount", minimum=1),
        "pirateSchedule": pirateSchedule,
        "pirateMissionChoice": None,
        "pirateMissionDayChoice": None,
        "pirateMissionNightChoice": None,
        "dayStart": asInt(dayStart, "dayStart", minimum=0, maximum=23),
        "dayEnd": asInt(dayEnd, "dayEnd", minimum=0, maximum=23),
        "nightStart": asInt(nightStart, "nightStart", minimum=0, maximum=23),
        "nightEnd": asInt(nightEnd, "nightEnd", minimum=0, maximum=23),
        "autoConvert": "y" if asBool(autoConvert, "autoConvert") else "n",
        "maxRandomWaitingTime": asInt(maxRandomWaitingTime, "maxRandomWaitingTime", minimum=0),
    }
    if pirateSchedule:
        config["pirateMissionDayChoice"] = asInt(pirateMissionDayChoice, "pirateMissionDayChoice", minimum=1, maximum=9)
        config["pirateMissionNightChoice"] = asInt(pirateMissionNightChoice, "pirateMissionNightChoice", minimum=1, maximum=9)
        missions = [config["pirateMissionDayChoice"], config["pirateMissionNightChoice"]]
    else:
        config["pirateMissionChoice"] = asInt(pirateMissionChoice, "pirateMissionChoice", minimum=1, maximum=9)
        missions = [config["pirateMissionChoice"]]
    if str(convertPerMission).strip().lower() == "all":
        config["convertPerMission"] = "all"
    else:
        config["convertPerMission"] = asInt(convertPerMission, "convertPerMission", minimum=0)

    # missions are shared by the whole account: a second task would wait for the first one's
    # missions and then race it for the fortress
    running = [p for p in updateProcessList(session) if p["action"] == "autoPirate"]
    if running:
        raise ValueError("autoPirate is already running for this account (pid {})".format(running[0]["pid"]))

    # the hardest mission needs the highest fortress level
    piracy_cities = getPiracyCities(session, max(missions))
    if not piracy_cities:
        raise ValueError("none of your cities has a pirate fortress able to do mission {}".format(max(missions)))
    first_city = piracyCities[0] if piracyCities else piracy_cities[0]
    first_city_id = first_city["id"] if isinstance(first_city, dict) else first_city
    # the task only reads the first city's id: keep the saved config small
    config["piracyCities"] = [{"id": asId(first_city_id, "piracyCities")}]
    return config


@task("autoPirate", prepare=prepare_autoPirate)
def do_pirate_missions(
    session,
    pirateCount,
    pirateSchedule=False,
    pirateMissionChoice=None,
    pirateMissionDayChoice=None,
    pirateMissionNightChoice=None,
    dayStart=10,
    dayEnd=18,
    nightStart=19,
    nightEnd=9,
    autoConvert="n",
    convertPerMission=0,
    maxRandomWaitingTime=0,
    piracyCities=None,
):
    cachedCityId = piracyCities[0]["id"] if piracyCities else None
    while pirateCount > 0:
        session.setStatus("Pirating for " + str(pirateCount) + " more runs")
        if pirateSchedule == True:
            pirateMissionChoice = getScheduledMission(
                dayStart, dayEnd, nightStart, nightEnd,
                pirateMissionDayChoice, pirateMissionNightChoice,
            )
            if pirateMissionChoice is None:
                session.setStatus("Outside of scheduled hours, waiting for the next range")
                wait(getSecondsUntilNextRange(dayStart, nightStart))
                continue
        pirateCount -= 1
        # try the last used fortress city first, fall back to a full scan if it's gone
        cachedCity = (
            getPiracyCityById(session, cachedCityId, pirateMissionChoice)
            if cachedCityId is not None
            else None
        )
        if cachedCity is not None:
            piracyCities = [cachedCity]
        else:
            piracyCities = getPiracyCities(session, pirateMissionChoice)
            if piracyCities == []:
                raise Exception(
                    "No city with pirate fortress capable of executing selected mission"
                )
        cachedCityId = piracyCities[0]["id"]
        html = session.post(
            city_url + str(piracyCities[0]["id"])
        )  # this is needed because for some reason you need to look at the town where you are sending a request from in the line below, before you send that request
        if (
            '"showPirateFortressShip":0' in html
        ):  # this is in case the user has manually run a capture run, in that case, there is no need to wait 150secs instead we can check every 5
            url = "view=pirateFortress&cityId={}&position=17&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1".format(
                piracyCities[0]["id"], piracyCities[0]["id"], actionRequest
            )
            html = session.post(url)
            wait(getCurrentMissionWaitingTime(html), maxRandomWaitingTime)
            pirateCount += 1  # don't count this as an iteration of the loop
            continue

        url = "action=PiracyScreen&function=capture&buildingLevel={0}&view=pirateFortress&cityId={1}&position=17&activeTab=tabBootyQuest&backgroundView=city&currentCityId={1}&templateView=pirateFortress&actionRequest={2}&ajax=1".format(
            piracyMissionToBuildingLevel[pirateMissionChoice],
            piracyCities[0]["id"],
            actionRequest,
        )
        html = session.post(url)

        if (
            "function=createCaptcha" in html or "js_captchaImage" in html
        ):
            try:
                for i in range(20):
                    session.setStatus("Resolving captcha " + str(i) + "/20")
                    if i == 19:
                        msg = "Failed to resolve captcha too many times, autoPirate has been terminated."
                        sendToBot(session, msg)
                        raise Exception("Failed to resolve captcha too many times")
                    picture = extract_captcha_image(html)
                    if picture is None:
                        picture = session.get(
                            "action=Options&function=createCaptcha",
                            fullResponse=True,
                        ).content
                    captcha = resolveCaptcha(session, picture)
                    if captcha == "Error":
                        session.setStatus("Retrying captcha " + str(i + 1) + "/20")
                        # The captcha could not be solved (local solver failed
                        # or the remote API rejected the image). Wait a moment
                        # and trigger a fresh capture request so we get a brand
                        # new captcha (or restore the fortress context) instead
                        # of re-trying against the same stale HTML.
                        time.sleep(5)
                        url = "action=PiracyScreen&function=capture&buildingLevel={0}&view=pirateFortress&cityId={1}&position=17&activeTab=tabBootyQuest&backgroundView=city&currentCityId={1}&templateView=pirateFortress&actionRequest={2}&ajax=1".format(
                            piracyMissionToBuildingLevel[pirateMissionChoice],
                            piracyCities[0]["id"],
                            actionRequest,
                        )
                        html = session.post(url)
                        if not (
                            "function=createCaptcha" in html
                            or "js_captchaImage" in html
                        ):
                            # the fortress is gone/not asking us for a captcha
                            # anymore; let the outer logic decide what to do
                            break
                        continue
                    session.setStatus("Got captcha: " + captcha)
                    session.post(city_url + str(piracyCities[0]["id"]))
                    params = {
                        "action": "PiracyScreen",
                        "function": "capture",
                        "cityId": piracyCities[0]["id"],
                        "position": "17",
                        "captchaNeeded": "1",
                        "buildingLevel": str(
                            piracyMissionToBuildingLevel[pirateMissionChoice]
                        ),
                        "captcha": captcha,
                        "activeTab": "tabBootyQuest",
                        "backgroundView": "city",
                        "currentCityId": piracyCities[0]["id"],
                        "templateView": "pirateFortress",
                        "actionRequest": actionRequest,
                        "ajax": "1",
                    }
                    html = session.post(params=params, noIndex=True)
                    if (
                        '"showPirateFortressShip":1' in html
                    ):  # if this is true, then the crew is still in the town, that means that the request didn't succeed
                        time.sleep(5)
                        continue
                    break
            except Exception:
                info = ""
                msg = "Error in:\n{}\nCause:\n{}".format(
                    info, traceback.format_exc()
                )
                sendToBot(session, msg)
                break
        if autoConvert.lower() == "y":
            convertCapturePoints(session, piracyCities, convertPerMission)
        wait(piracyMissionWaitingTime[pirateMissionChoice], maxRandomWaitingTime)

@configurator
def autoPirate(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    banner()

    if not (PIRATE_DECAPTCHA_LOCAL and LOCAL_DECAPTCHA):
        print("💡 TIP: You can process captchas locally! Run `pip install onnxruntime` to move inference to your client.")
        print("This feature is not available if you are using the precombile binary for Windows!\n\n")
        print("{}⚠️ USING THIS FEATURE WILL EXPOSE YOUR IP ADDRESS TO A THIRD PARTY FOR CAPTCHA SOLVING ⚠️{}\n\n".format(bcolors.WARNING, bcolors.ENDC))
    else:
        print("{}[SUCCESS]{} You are using local decaptcha!\n\n".format(bcolors.GREEN, bcolors.ENDC))

    print("How many pirate missions should I do? (min = 1)")
    pirateCount = read(min=1, digit=True)
    print("Should I schedule pirate missions by the time of day? (y/N)")
    scheduleInput = read(values=["y", "Y", "n", "N", ""])
    pirateMissionDayChoice = None
    pirateMissionNightChoice = None
    dayStart = None
    dayEnd = None
    nightStart = None
    nightEnd = None
    pirateMissionChoice = None

    if scheduleInput.lower() == "y":
        pirateSchedule = True
        print(
            """Which pirate mission should I do at daytime? (Default mission)
    (1) 2m 30s
    (2) 7m 30s
    (3) 15m
    (4) 30m
    (5) 1h
    (6) 2h
    (7) 4h
    (8) 8h
    (9) 16h
    """
        )
        pirateMissionDayChoice = read(min=1, max=9, digit=True)
        print(
            """At which hours should I operate at daytime? (Default: 9 hours from 10 till 18)
        """
        )
        print("From: ")
        dayStart = read(min=0, max=23, digit=True, default=10)

        print("Till: ")
        dayEnd = read(min=0, max=23, digit=True, default=18)

        print(
            """Which pirate mission should I do at night time?
        (1) 2m 30s
        (2) 7m 30s
        (3) 15m
        (4) 30m
        (5) 1h
        (6) 2h
        (7) 4h
        (8) 8h
        (9) 16h
        """
        )
        pirateMissionNightChoice = read(min=1, max=9, digit=True)

        print(
            """At which hours should I operate at night time? (Default: 15 hours from 19 till 9): 
        """
        )
        print("From: ")
        nightStart = read(min=0, max=23, digit=True, default=19)

        print("Till: ")
        nightEnd = read(min=0, max=23, digit=True, default=9)
    else:
        pirateSchedule = False
        print(
            """Which pirate mission should I do?
    (1) 2m 30s
    (2) 7m 30s
    (3) 15m
    (4) 30m
    (5) 1h
    (6) 2h
    (7) 4h
    (8) 8h
    (9) 16h
    """
        )
        pirateMissionChoice = read(min=1, max=9, digit=True)
    if pirateSchedule == True:
        pirateMissionChoice = getScheduledMission(
            dayStart, dayEnd, nightStart, nightEnd,
            pirateMissionDayChoice, pirateMissionNightChoice,
        )
        if pirateMissionChoice is None:
            pirateMissionChoice = pirateMissionDayChoice
    print(
        "Do you want me to automatically convert capture points to crew strength? (Y|N)"
    )
    autoConvert = read(values=["y", "Y", "n", "N"])
    convertPerMission = 0
    if autoConvert.lower() == "y":
        print(
            'How many points should I convert every time I do a mission? (Type "all" to convert all points at once)'
        )
        convertPerMission = read(min=0, additionalValues=["all"], digit=True)
    print(
        "Enter a maximum additional random waiting time between missions in seconds. (min = 0)"
    )
    maxRandomWaitingTime = read(min=0, digit=True)
    piracyCities = getPiracyCities(session, pirateMissionChoice)
    if piracyCities == []:
        print(
            "You do not have any city with a pirate fortress capable of executing this mission!"
        )
        enter()
        return None

    print(
        "YAAAAAR!"
    )  # get data for options such as auto-convert to crew strength, time intervals, number of piracy attempts... ^^
    enter()
    
    return {
        "session": session,
        "pirateCount": pirateCount,
        "pirateSchedule": pirateSchedule,
        "pirateMissionChoice": pirateMissionChoice,
        "pirateMissionDayChoice": pirateMissionDayChoice,
        "pirateMissionNightChoice": pirateMissionNightChoice,
        "dayStart": dayStart,
        "dayEnd": dayEnd,
        "nightStart": nightStart,
        "nightEnd": nightEnd,
        "autoConvert": autoConvert,
        "convertPerMission": convertPerMission,
        "maxRandomWaitingTime": maxRandomWaitingTime,
        "piracyCities": piracyCities
    }


def _is_png_bytes(image):
    """True only if image is a non-empty PNG byte string.

    The captcha solvers expect the actual PNG image, not the surrounding HTML
    or a redirect/login page. Returning "Error" (so the loop can retry) is
    safer than sending garbage to the API and getting a silent 500."""
    try:
        return (
            isinstance(image, (bytes, bytearray))
            and len(image) > 8
            and bytes(image[:8]) == b"\x89PNG\r\n\x1a\n"
        )
    except Exception:
        return False


def resolveCaptcha(session, picture):
    session_data = session.getSessionData()
    if (
        "decaptcha" not in session_data
        or session_data["decaptcha"]["name"] == "default"
    ):
        if not _is_png_bytes(picture):
            return "Error"
        if PIRATE_DECAPTCHA_LOCAL and LOCAL_DECAPTCHA:
            try:
                return get_captcha_string(picture)
            except Exception:
                pass  # Fall back to remote solving if local decaptcha fails
        if _is_png_bytes(picture):
            try:
                return getPiratesCaptchaSolution(session, picture)
            except Exception as e:
                _logger.warning(
                    "Remote pirates captcha API failed: %s" % e
                )
                return "Error"
        return "Error"
    elif session_data["decaptcha"]["name"] == "custom":
        files = {"upload_file": picture}
        captcha = requests.post(
            "{0}".format(session_data["decaptcha"]["endpoint"]), files=files
        ).text
        return captcha
    elif session_data["decaptcha"]["name"] == "9kw.eu":
        credits = requests.get(
            "https://www.9kw.eu/index.cgi?action=usercaptchaguthaben&apikey={}".format(
                session_data["decaptcha"]["relevant_data"]["apiKey"]
            )
        ).text
        if int(credits) < 10:
            raise Exception("You do not have enough 9kw.eu credits!")
        captcha_id = requests.post(
            "https://www.9kw.eu/index.cgi?action=usercaptchaupload&apikey={}".format(
                session_data["decaptcha"]["relevant_data"]["apiKey"]
            ),
            headers={"Content-Type": "multipart/form-data"},
            files={"file-upload-01": picture},
        ).text
        while True:
            captcha_result = requests.get(
                "https://www.9kw.eu/index.cgi?action=usercaptchacorrectdata&id={}&apikey={}".format(
                    captcha_id, session_data["decaptcha"]["relevant_data"]["apiKey"]
                )
            ).text
            if captcha_result != "":
                return captcha_result.upper()
            wait(5)
    elif session_data["decaptcha"]["name"] == "telegram":
        sendToBot(session, "Please solve the captcha", Photo=picture)
        captcha_time = time.time()
        while True:
            response = getUserResponse(session, fullResponse=True)
            if len(response) == 0:
                time.sleep(5)
                continue
            response = response[-1]
            if response["date"] > captcha_time:
                return response["text"]
            time.sleep(5)


def getPiracyCityById(session, city_id, pirateMissionChoice):
    """Checks a single city for a pirate fortress capable of the given mission.
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : str | int
    pirateMissionChoice : str

    Returns
    -------
    city : dict | None
        the city (as returned by getCity) if it has a usable pirate fortress, None otherwise
    """
    html = session.get(city_url + str(city_id))
    city = getCity(html)
    for building in city["position"]:
        if (
            building["building"] == "pirateFortress"
            and building["level"] >= piracyMissionToBuildingLevel[pirateMissionChoice]
        ):
            return city
    return None


def getPiracyCities(session, pirateMissionChoice):
    """Gets all user's cities which have a pirate fortress in them
    Parameters
    ----------
    session : ikabot.web.session.Session

    Returns
    -------
    piracyCities : list[dict]
    """
    cities_ids = getIdsOfCities(session)[0]
    piracyCities = []
    for city_id in cities_ids:
        city = getPiracyCityById(session, city_id, pirateMissionChoice)
        if city is not None:
            piracyCities.append(city)
    return piracyCities


def getPirateFortressHtml(session, cityId):
    """Gets the crew tab of the pirate fortress. The fortress always sits on position 17
    Parameters
    ----------
    session : ikabot.web.session.Session
    cityId : int
        id of a city which has a pirate fortress in it

    Returns
    -------
    html : str
    """
    params = {
        "view": "pirateFortress",
        "activeTab": "tabCrew",
        "cityId": cityId,
        "position": 17,
        "backgroundView": "city",
        "currentCityId": cityId,
        "templateView": "pirateFortress",
        "actionRequest": actionRequest,
        "ajax": 1,
    }
    return session.post(params=params)


def getPirateFortressPoints(session, cityId):
    """Gets the capture points and the crew strength of the account. Both are shared by
    every city, so any city with a pirate fortress can be used to read them
    Parameters
    ----------
    session : ikabot.web.session.Session
    cityId : int
        id of a city which has a pirate fortress in it

    Returns
    -------
    (capturePoints, crewStrength) : tuple
        None if the fortress did not report them
    """
    html = getPirateFortressHtml(session, cityId)
    capturePoints = re.search(r'\\"capturePoints\\":\\"(\d+)\\"', html)
    # crewPoints only counts the crew converted from capture points, the strength the
    # game shows also includes the basic and the bonus crew
    crewStrength = re.search(r'\\"completeCrewPoints\\":(\d+)', html)
    if capturePoints is None or crewStrength is None:
        return None
    return int(capturePoints.group(1)), int(crewStrength.group(1))


def convertCapturePoints(session, piracyCities, convertPerMission):
    """Converts all the users capture points into crew strength
    Parameters
    ----------
    session : ikabot.web.session.Session
    piracyCities: a list containing all cities which have a pirate fortress
    """
    html = getPirateFortressHtml(session, piracyCities[0]["id"])
    rta = re.search(r'\\"capturePoints\\":\\"(\d+)\\"', html)
    capturePoints = int(rta.group(1))
    if convertPerMission == "all":
        convertPerMission = capturePoints
    if "conversionProgressBar" in html:  # if a conversion is still in progress
        return
    data = {
        "action": "PiracyScreen",
        "function": "convert",
        "view": "pirateFortress",
        "cityId": piracyCities[0]["id"],
        "islandId": piracyCities[0]["islandId"],
        "activeTab": "tabCrew",
        "crewPoints": str(int(convertPerMission / 10)),
        "position": "17",
        "backgroundView": "city",
        "currentCityId": piracyCities[0]["id"],
        "templateView": "pirateFortress",
        "actionRequest": actionRequest,
        "ajax": "1",
    }
    html = session.post(params=data, noIndex=True)


def getCurrentMissionWaitingTime(html):
    try:
        match = re.search(r'ongoingMissionTimeRemaining\\":(\d+),', html)
        assert (
            match
        ), "Couldn't find remaining ongoing mission time, did you run a pirate mission manually?"
        return int(match.group(1))
    except: # In case we can not find current mission waiting time, just sleep for 10 mins (Not a perfect solution)
        return 10 * 60

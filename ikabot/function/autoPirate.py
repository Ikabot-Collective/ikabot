#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gettext
import sys
import requests
import re
import traceback
import time
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.gui import *
from ikabot.config import *
from ikabot.helpers.getJson import *
from ikabot.helpers.botComm import *
from ikabot.helpers.varios import wait
from ikabot.helpers.process import run


t = gettext.translation('buyResources',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def autoPirate(session, event, stdin_fd, predetermined_input):
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
    banner()
    try:
        if not isWindows:
            path = run('which nslookup')
            is_installed = re.search(r'/.*?/nslookup', path) != None
            if is_installed is False:
                print('you must first install nslookup')
                enter()
                event.set()
                return

        print('{}⚠️ USING THIS FEATURE WILL EXPOSE YOUR IP ADDRESS TO A THIRD PARTY FOR CAPTCHA SOLVING ⚠️{}\n\n'.format(bcolors.WARNING, bcolors.ENDC))
        print('How many pirate missions should I do? (min = 1)')
        pirateCount = read(min = 1, digit = True)
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
        pirateMissionChoice = read(min = 1, max = 9, digit = True)
        print('Do you want me to automatically convert capture points to crew strength? (Y|N)')
        autoConvert = read(values = ['y','Y','n','N'])
        if autoConvert.lower() == 'y':
            print('How many points should I convert every time I do a mission? (Type "all" to convert all points at once)')
            convertPerMission = read(min = 0, additionalValues = ['all'], digit = True)
        print('Enter a maximum additional random waiting time between missions in seconds. (min = 0)')
        maxRandomWaitingTime = read(min = 0, digit = True)
        piracyCities = getPiracyCities(session, pirateMissionChoice)
        if piracyCities == []:
            print('You do not have any city with a pirate fortress capable of executing this mission!')
            enter()
            event.set()
            return



        print('YAAAAAR!') #get data for options such as auto-convert to crew strength, time intervals, number of piracy attempts... ^^
        enter()
    except KeyboardInterrupt:
        event.set()
        return
    event.set()
    try:
        while (pirateCount > 0):
            pirateCount -= 1
            piracyCities = getPiracyCities(session, pirateMissionChoice) # this is done again inside the loop in case the user destroys / creates another pirate fortress while this module is running
            if piracyCities == []:
                raise Exception('No city with pirate fortress capable of executing selected mission')
            html = session.post(city_url + str(piracyCities[0]['id'])) # this is needed because for some reason you need to look at the town where you are sending a request from in the line below, before you send that request
            if '"showPirateFortressShip":0' in html: # this is in case the user has manually run a capture run, in that case, there is no need to wait 150secs instead we can check every 5
                url = 'view=pirateFortress&cityId={}&position=17&backgroundView=city&currentCityId={}&actionRequest={}&ajax=1'.format(piracyCities[0]['id'], piracyCities[0]['id'], actionRequest)
                html = session.post(url)
                wait(getCurrentMissionWaitingTime(html), maxRandomWaitingTime)
                pirateCount += 1 # don't count this as an iteration of the loop
                continue
                                                       #buildingLevel=[level of pirate fortress for certain mission], for example for mission 2 you'll put 3 here because that's the level of the piratefortress needed to run that mission, max level can be accessed with piracyCities[0]['position'][17]['level']
            url = 'action=PiracyScreen&function=capture&buildingLevel={0}&view=pirateFortress&cityId={1}&position=17&activeTab=tabBootyQuest&backgroundView=city&currentCityId={1}&templateView=pirateFortress&actionRequest={2}&ajax=1'.format(piracyMissionToBuildingLevel[pirateMissionChoice], piracyCities[0]['id'], actionRequest)
            html = session.post(url)
            
            if 'function=createCaptcha' in html:
                try:
                    for i in range(20):
                        if i == 19:
                            raise Exception("Failed to resolve captcha too many times")
                        picture = session.get('action=Options&function=createCaptcha',fullResponse=True).content
                        captcha = resolveCaptcha(session, picture)
                        if captcha == 'Error':
                            continue
                        session.post(city_url + str(piracyCities[0]['id']))
                        params = {'action': 'PiracyScreen', 'function': 'capture', 'cityId': piracyCities[0]['id'], 'position': '17', 'captchaNeeded': '1', 'buildingLevel': str(piracyMissionToBuildingLevel[pirateMissionChoice]), 'captcha': captcha, 'activeTab': 'tabBootyQuest', 'backgroundView': 'city', 'currentCityId': piracyCities[0]['id'], 'templateView': 'pirateFortress', 'actionRequest': actionRequest, 'ajax': '1'}
                        html = session.post(payloadPost = params, noIndex = True)
                        if '"showPirateFortressShip":1' in html: #if this is true, then the crew is still in the town, that means that the request didn't succeed
                            continue
                    
                        break
                except Exception:
                    info=''
                    msg = _('Error in:\n{}\nCause:\n{}').format(info, traceback.format_exc())
                    sendToBot(session, msg)
                    break
            if autoConvert.lower() == 'y':
                convertCapturePoints(session, piracyCities, convertPerMission)
            wait(piracyMissionWaitingTime[pirateMissionChoice], maxRandomWaitingTime)

    except Exception:
        event.set()
        return

def resolveCaptcha(session, picture):
    session_data = session.getSessionData()
    if 'decaptcha' not in session_data or session_data['decaptcha']['name'] == 'default':
        text = run('nslookup -q=txt ikagod.twilightparadox.com ns2.afraid.org')
        address = text.split('"')[1] 

        files = {'upload_file': picture}
        captcha = requests.post('http://{0}'.format(address), files=files).text
        return captcha
    elif session_data['decaptcha']['name'] == 'custom':
        files = {'upload_file': picture}
        captcha = requests.post('{0}'.format(session_data['decaptcha']['endpoint']), files=files).text
        return captcha
    elif session_data['decaptcha']['name'] == '9kw.eu':
        credits = requests.get("https://www.9kw.eu/index.cgi?action=usercaptchaguthaben&apikey={}".format(session_data['decaptcha']['relevant_data']['apiKey'])).text
        if int(credits) < 10:
            raise Exception('You do not have enough 9kw.eu credits!')
        captcha_id = requests.post("https://www.9kw.eu/index.cgi?action=usercaptchaupload&apikey={}".format(session_data['decaptcha']['relevant_data']['apiKey']), headers = {'Content-Type' : 'multipart/form-data'}, files = { 'file-upload-01' : picture}).text
        while True:
            captcha_result = requests.get("https://www.9kw.eu/index.cgi?action=usercaptchacorrectdata&id={}&apikey={}".format(captcha_id, session_data['decaptcha']['relevant_data']['apiKey'])).text
            if captcha_result != '':
                return captcha_result.upper()
            wait(5)
    elif session_data['decaptcha']['name'] == 'telegram':
        sendToBot(session, 'Please solve the captcha', Photo = picture)
        captcha_time = time.time()
        while(True):
            response = getUserResponse(session, fullResponse = True)
            if response is []:
                time.sleep(5)
                continue
            response = response[-1]
            if response['date'] > captcha_time:
                return response['text']
            time.sleep(5)


    
    

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
		html = session.get(city_url + city_id)
		city = getCity(html)
		for pos, building in enumerate(city['position']):
			if building['building'] == 'pirateFortress' and building['level'] >= piracyMissionToBuildingLevel[pirateMissionChoice]:
				piracyCities.append(city)
				break
	return piracyCities

def convertCapturePoints(session, piracyCities, convertPerMission):
    """Converts all the users capture points into crew strength
	Parameters
	----------
	session : ikabot.web.session.Session
    piracyCities: a list containing all cities which have a pirate fortress
	"""
    html = session.get('view=pirateFortress&activeTab=tabCrew&cityId={0}&position=17&backgroundView=city&currentCityId={0}&templateView=pirateFortress'.format(piracyCities[0]['id']))
    rta = re.search(r'\\"capturePoints\\":\\"(\d+)\\"', html)
    capturePoints = int(rta.group(1))
    if convertPerMission == 'all':
        convertPerMission = capturePoints
    if 'conversionProgressBar' in html: #if a conversion is still in progress
        return
    data = {'action': 'PiracyScreen', 'function': 'convert', 'view': 'pirateFortress', 'cityId': piracyCities[0]['id'], 'islandId': piracyCities[0]['islandId'], 'activeTab': 'tabCrew', 'crewPoints': str(int(convertPerMission/10)), 'position': '17', 'backgroundView': 'city', 'currentCityId': piracyCities[0]['id'], 'templateView': 'pirateFortress', 'actionRequest': actionRequest, 'ajax': '1'}
    html = session.post(payloadPost = data, noIndex = True)

def getCurrentMissionWaitingTime(html):
    match = re.search(r'missionProgressTime\\\\">(.*?)<\\\\\/div>', html)
    if match is None:
        return 0
    else:
        time_string = match.group(1)
        hours = re.search(r'(\d+)h', time_string)
        if hours is None:
            hours = 0
        else:
            hours = int(hours.group(1)) * 3600
        minutes = re.search(r'(\d+)m', time_string)
        if minutes is None:
            minutes = 0
        else:
            minutes = int(minutes.group(1)) * 60
        seconds = re.search(r'(\d+)s', time_string)
        if seconds is None:
            seconds = 0
        else:
            seconds = int(seconds.group(1)) * 1
        return hours + minutes + seconds

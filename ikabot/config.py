#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import locale
import os

# Version is changed automatically by the release pipeline
IKABOT_VERSION = "7.2.1"


IKABOT_VERSION_TAG = "v" + IKABOT_VERSION




update_msg = ""

isWindows = os.name == "nt"


LOGS_DIRECTORY_FILE = os.getenv("temp") + "/ikabot.log" if isWindows else "/tmp/ikabot.log"
DEFAULT_LOG_LEVEL = 30 # Warning

publicAPIServerDomain = "ikagod.twilightparadox.com"
do_ssl_verify = True
ids_cache = None
cities_cache = None
has_params = False
menu_cities = ""
infoUser = ""
ikaFile = ".ikabot"
city_url = "view=city&cityId="
island_url = "view=island&islandId="
prompt = " >>  "
materials_names = ["Wood", "Wine", "Marble", "Crystal", "Sulfur"]
materials_names_english = ["Wood", "Wine", "Marble", "Crystal", "Sulfur"]
miracle_names_english = [
    "",
    "Hephaestus' Forge",
    "Hades' Holy Grove",
    "Demeter's gardens",
    "Athena's Parthenon",
    "Temple of Hermes",
    "Ares' Stronghold",
    "Temple of Poseidon",
    "Colossus",
]
materials_names_tec = ["wood", "wine", "marble", "glass", "sulfur"]
material_img_hash = [
    "19c3527b2f694fb882563c04df6d8972",
    "c694ddfda045a8f5ced3397d791fd064",
    "bffc258b990c1a2a36c5aeb9872fc08a",
    "1e417b4059940b2ae2680c070a197d8c",
    "9b5578a7dfa3e98124439cca4a387a61",
]
tradegoods_names = [
    "Saw mill",
    "Vineyard",
    "Quarry",
    "Crystal Mine",
    "Sulfur Pit",
]
ConnectionError_wait = 5 * 60
actionRequest = "REQUESTID"
piracyMissionToBuildingLevel = {
    1: 1,
    2: 3,
    3: 5,
    4: 7,
    5: 9,
    6: 11,
    7: 13,
    8: 15,
    9: 17,
}
piracyMissionWaitingTime = {
    1: 150,
    2: 450,
    3: 900,
    4: 1800,
    5: 3600,
    6: 7200,
    7: 14400,
    8: 28800,
    9: 57600,
}
predetermined_input = []




debugON_alertAttacks = False
debugON_alertLowWine = False
debugON_donationBot = False
debugON_searchForIslandSpaces = False
debugON_loginDaily = False
debugON_enviarVino = False
debugON_sendResources = False
debugON_constructionList = False
debugON_buyResources = False
debugON_activateMiracle = False

MAXIMUM_CITY_NAME_LENGTH = 20
SECONDS_IN_HOUR = 60 * 60

# Default values for dynamic settings
enable_CustomPort = False

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.4",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.5",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36 Edg/109.0.1518.5",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.3",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.3",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.",
    "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36 Edg/109.0.1518.14",
    "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36 Edg/109.0.1518.10",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Geck",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.2",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.",
]

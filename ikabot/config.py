#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import random
import locale
import gettext


local = locale.setlocale(locale.LC_ALL, '')
if 'es_' in local:
    languages = ['es']
else:
    languages = ['en']
languages = ['none']

localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
t = gettext.translation('config', localedir, languages=languages, fallback=True)
_ = t.gettext

# only use common browsers
if random.randint(0, 1) == 0:
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
else:
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0'

update_msg = ''

isWindows = os.name == 'nt'

do_ssl_verify = True
ids_cache = None
cities_cache = None
has_params = False
menu_cities = ''
infoUser = ''
ikaFile = '.ikabot'
city_url = 'view=city&cityId='
island_url = 'view=island&islandId='
prompt = ' >>  '
materials_names = [_('Wood'), _('Wine'), _('Marble'), _('Cristal'), _('Sulfur')]
materials_names_english = ['Wood', 'Wine', 'Marble', 'Cristal', 'Sulfur']
materials_names_tec = ['wood', 'wine', 'marble', 'glass', 'sulfur']
material_img_hash = ['19c3527b2f694fb882563c04df6d8972', 'c694ddfda045a8f5ced3397d791fd064', 'bffc258b990c1a2a36c5aeb9872fc08a', '1e417b4059940b2ae2680c070a197d8c', '9b5578a7dfa3e98124439cca4a387a61']
tradegoods_names = [_('Saw mill'), _('Vineyard'), _('Quarry'), _('Crystal Mine'), _('Sulfur Pit')]
ConnectionError_wait = 5 * 60
actionRequest = 'REQUESTID'
piracyMissionToBuildingLevel = {1: 1, 2: 3, 3: 5, 4: 7, 5: 9, 6: 11, 7: 13, 8: 15, 9: 17}
piracyMissionWaitingTime = {1: 150, 2: 450, 3: 900, 4: 1800, 5: 3600, 6: 7200, 7: 14400, 8: 28800, 9: 57600}
predetermined_input = []
logLevelsText = ["DEBUG", "INFO", "WARN", "ERROR"]
class logLevels:
    DEBUG = 0
    INFO  = 1
    WARN  = 2
    ERROR = 3
logLevel = logLevels.WARN
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

#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import gettext
import traceback
from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.varios import *
from ikabot.helpers.botComm import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.getJson import getCity
from ikabot.helpers.signals import setInfoSignal

t = gettext.translation('investigate',
                        localedir,
                        languages=languages,
                        fallback=True)
_ = t.gettext

def get_studies(session):
	html = session.get()
	city = getCity(html)
	city_id = city['id']
	url = 'view=researchAdvisor&oldView=updateGlobalData&cityId={0}&backgroundView=city&currentCityId={0}&templateView=researchAdvisor&actionRequest={1}&ajax=1'.format(city_id, actionRequest)
	resp = session.post(url)
	resp = json.loads(resp, strict=False)
	return resp[2][1]

def study(session, studies, num_study):
	html = session.get()
	city = getCity(html)
	city_id = city['id']
	research_type = studies['js_researchAdvisorChangeResearchType{}'.format(num_study)]['ajaxrequest'].split('=')[-1]
	url = 'action=Advisor&function=doResearch&actionRequest={}&type={}&backgroundView=city&currentCityId={}&templateView=researchAdvisor&ajax=1'.format(actionRequest, research_type, city_id)
	session.post(url)

def investigate(session, event, stdin_fd):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	event : multiprocessing.Event
	stdin_fd: int
	"""
	sys.stdin = os.fdopen(stdin_fd)
	try:
		banner()

		studies = get_studies(session)
		keys = list(studies.keys())
		num_studies = len( [ key for key in keys if 'js_researchAdvisorChangeResearchTypeTxt' in key ] )

		available = []
		for num_study in range(num_studies):
			if 'js_researchAdvisorProgressTxt{}'.format(num_study) in studies:
				available.append(num_study)

		if len(available) == 0:
			print(_('There are no available studies.'))
			enter()
			event.set()
			return

		print(_('Which one do you wish to study?'))
		print('0) None')
		for index, num_study in enumerate(available):
			print('{:d}) {}'.format(index+1, studies['js_researchAdvisorNextResearchName{}'.format(num_study)]))
		choice = read(min=0, max=len(available))

		if choice == 0:
			event.set()
			return

		study(session, studies, available[choice-1])
		print(_('Done.'))
		enter()
		event.set()

	except KeyboardInterrupt:
		event.set()
		return

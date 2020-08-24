#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import psutil
import subprocess
from ikabot.config import *
from ikabot.helpers.signals import deactivate_sigint

def set_child_mode(session):
	"""
	Parameters
	----------
	session : ikabot.web.session.Session
	"""
	session.padre = False
	deactivate_sigint()

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read()

def updateProcessList(session, programprocesslist = []):
	"""This function will return data about all the active ikabot processes. If it is passed the ``programprocesslist`` argument, it will write new processes from that list to the .ikabot file
	Parameters
	----------
	session : ikabot.web.session.Session
		Session object
	programprocesslist : list[dict]
		a list of dictionaries containing relevant data about a running ikabot process ('pid', 'proxies' and 'action')

	Returns
	-------
	runningIkabotProcessList : list[dict]
		a list of dictionaries containing relevant data about a running ikabot process ('pid', 'proxies' and 'action')
	"""
	# read from file
	sessionData = session.getSessionData()
	try:
		fileList = sessionData['processList']
	except KeyError:
		fileList = []

	# check it's still running
	runningIkabotProcessList = []
	ika_process = psutil.Process(pid = os.getpid()).name()
	for process in fileList:
		try:
			proc = psutil.Process(pid = process['pid'])
		except psutil.NoSuchProcess:
			continue

		# windows doesn't support the status method
		isAlive = True if isWindows else proc.status() != 'zombie'

		if proc.name() == ika_process and isAlive:
			runningIkabotProcessList.append(process)

	# add new to the list and write to file only if it's given
	for process in programprocesslist:
		if process not in runningIkabotProcessList:
			runningIkabotProcessList.append(process)

	# write to file
	sessionData['processList'] = runningIkabotProcessList
	session.setSessionData(sessionData)

	return runningIkabotProcessList

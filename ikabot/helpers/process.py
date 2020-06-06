#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import psutil
import json
from ikabot.config import *
from ikabot.helpers.signals import deactivate_sigint

def set_child_mode(s):
	s.padre = False
	deactivate_sigint()
	s.login()

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read()

def updateProcessList(s, programprocesslist = []):
	# read from file
	sessionData = s.getSessionData()
	try:
		fileList = sessionData['processList']
	except KeyError:
		fileList = []

	# check it's still running
	runningIkabotProcessList = []
	ika_process = 'python.exe' if isWindows else 'ikabot'
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
	s.setSessionData(sessionData)
	
	return runningIkabotProcessList

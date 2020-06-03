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
	## read from file
	fileData = s.getFileData()
	try:
		fileList = fileData['processList']
	except Exception:
		fileList = []


	##check it's good
	runningIkabotProcessList = []
	for process in fileList:
		if isWindows:
			try:
				if psutil.Process(pid = process['pid']).name() == 'python.exe':
					runningIkabotProcessList.append(process)
				else:
					continue
			except Exception:
				continue
		else:
			try:
				if psutil.Process(pid = process['pid']).name() == 'ikabot':
					runningIkabotProcessList.append(process)
				else:
					continue
			except Exception:
				continue



	## add new to the list and write to file only if it's given
	for process in programprocesslist:
		if process not in runningIkabotProcessList:
			runningIkabotProcessList.append(process)

	## write to file
	fileData['processList'] = runningIkabotProcessList
	s.setFileData(fileData)
	
	return runningIkabotProcessList




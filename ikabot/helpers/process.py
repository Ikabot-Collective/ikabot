#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
from ikabot.helpers.signals import deactivate_sigint

def set_child_mode(s):
	s.padre = False
	deactivate_sigint()
	s.login()

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read()

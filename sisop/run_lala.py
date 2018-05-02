#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess

def run(command):
	return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

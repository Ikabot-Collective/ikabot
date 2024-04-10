#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import subprocess

import psutil

from ikabot.config import *
from ikabot.helpers.signals import deactivate_sigint
from ikabot.helpers.varios import normalizeDicts


def set_child_mode(session):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    """
    session.padre = False
    deactivate_sigint()


def run(command):
    ret = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.read()
    try:
        return ret.decode("utf-8").strip()
    except Exception:
        return ret


def updateProcessList(session, programprocesslist=[]):
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
        fileList = sessionData["processList"]
    except KeyError:
        fileList = []

    # check it's still running
    runningIkabotProcessList = []
    ika_process = psutil.Process(pid=os.getpid()).name()
    for process in fileList:
        try:
            proc = psutil.Process(pid=process["pid"])
        except psutil.NoSuchProcess:
            continue

        # windows doesn't support the status method
        isAlive = True if isWindows else proc.status() != "zombie"

        if proc.name() == ika_process and isAlive:
            runningIkabotProcessList.append(process)

    # add new to the list and write to file only if it's given
    for process in programprocesslist:
        if process not in runningIkabotProcessList:
            runningIkabotProcessList.append(process)

    # check if all proceses have new status field
    if len([p for p in runningIkabotProcessList if "status" not in p]) == len(
        runningIkabotProcessList
    ) and len(runningIkabotProcessList):
        runningIkabotProcessList[0]["status"] = "running"

    # write to file
    sessionData["processList"] = runningIkabotProcessList
    session.setSessionData(sessionData)

    # normalize process list (all processes must have properties pid, action, date and status)
    normalized_processes = normalizeDicts(runningIkabotProcessList)
    # remove dupes by pid
    return list({d["pid"]: d for d in normalized_processes}.values())

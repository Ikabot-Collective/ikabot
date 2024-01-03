#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import gettext
import sys
import datetime
from ikabot.helpers.pedirInfo import read, enter
from ikabot.helpers.gui import *
from ikabot.config import *
from ikabot.helpers.process import updateProcessList, run

t = gettext.translation('killTasks', localedir, languages=languages, fallback=True)
_ = t.gettext


def killTasks(session, event, stdin_fd, predetermined_input):
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
    try:
        while True:
            banner()
            process_list = updateProcessList(session)
            process_list = [process for process in process_list if process['action'] != 'killTasks']
            if len(process_list) == 0:
                print(_('There are no tasks running'))
                enter()
                event.set()
                return
            print('Which task do you wish to kill?\n')
            print('(0) Exit')
            for process in process_list:
                if 'date' in process:
                    print("({}) {:<35}{:>20}".format(process_list.index(process) + 1, process['action'], datetime.datetime.fromtimestamp(process['date']).strftime('%b %d %H:%M:%S')))
                else:
                    print("({}) {:<35}".format(process_list.index(process) + 1, process['action'],))
            choise = read(min=0, max=len(process_list), digit=True)
            if choise == 0:
                event.set()
                return
            else:
                if isWindows:
                    run("taskkill /F /PID {}".format(process_list[choise-1]['pid']))
                else:
                    run("kill -9 {}".format(process_list[choise-1]['pid']))
    except KeyboardInterrupt:
        event.set()
        return

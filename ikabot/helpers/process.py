#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import subprocess

import psutil

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
    ret = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.read()
    try:
        return ret.decode('utf-8').strip()
    except Exception:
        return ret

class IkabotProcessListManager:
    def __init__(self, session):
        """
        Init processes -> reads and updates the file
        :param session: ikabot.web.session.Session
        """
        self.__session = session
        self.__process_dict = self.__read_from_files()
        self.__write_to_file()

    def __read_from_files(self):
        """
        Reads all process from file.
        :return: dict[pid -> dict of proces]
        """
        # read from file
        try:
            fileList = (self.__session.getSessionData())['processList']
        except KeyError:
            fileList = []

        # check it's still running
        running_ikabot_processes = []
        ika_process = psutil.Process(pid=os.getpid()).name()
        for process in fileList:
            try:
                proc = psutil.Process(pid=process['pid'])
            except psutil.NoSuchProcess:
                continue

            # windows doesn't support the status method
            isAlive = True if isWindows else proc.status() != 'zombie'

            if proc.name() == ika_process and isAlive:
                running_ikabot_processes.append(process)


        return {p['pid']: p for p in running_ikabot_processes}

    def __write_to_file(self):
        """
        Writes processes list to the file
        :return: None
        """
        session_data = (self.__session.getSessionData())
        session_data['processList'] = self.get_process_list()
        self.__session.setSessionData(session_data)

    def get_process_list(self):
        return [p for p in self.__process_dict.values()]

    def add_process(self, process):
        self.__process_dict[process['pid']] = process
        self.__write_to_file()

    def update_process(self, process):
        self.__process_dict[process['pid']] = process
        self.__write_to_file()

    def print_proces_table(self):
        process_list = self.get_process_list()
        print()
        if len(process_list) == 0:
            return

        # Insert table header
        table = process_list.copy()
        table.insert(0,{'pid':'pid', 'action':'task','date':'date','status':'status'})
        # Get max length of strings in each category (date is always going to be 15)
        maxPid, maxAction, maxStatus = [max(i) for i in [[len(str(r['pid'])) for r in table], [len(str(r['action'])) for r in table], [len(str(r['status'])) for r in table]]]
        # Print header
        print('|{:^{maxPid}}|{:^{maxAction}}|{:^15}|{:^{maxStatus}}|'.format(table[0]['pid'], table[0]['action'], table[0]['date'], table[0]['status'], maxPid=maxPid, maxAction=maxAction, maxStatus=maxStatus))
        # Print process list
        [print('|{:^{maxPid}}|{:^{maxAction}}|{:^15}|{:^{maxStatus}}|'.format(r['pid'], r['action'], datetime.datetime.fromtimestamp(r['date']).strftime('%b %d %H:%M:%S'), r['status'], maxPid=maxPid, maxAction=maxAction, maxStatus=maxStatus)) for r in process_list]
        print('')


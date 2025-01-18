#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime

from ikabot.config import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import enter, read
from ikabot.helpers.process import run, updateProcessList

from typing import TYPE_CHECKING, TypedDict, Union
if TYPE_CHECKING:
    from ikabot.web.session import Session

def killTasks(session: Session):
    while True:
        banner()
        process_list = updateProcessList(session)
        process_list = [
            process for process in process_list if process["action"] != "killTasks"
        ]
        if len(process_list) == 0:
            print("There are no tasks running")
            enter()
            return
        print("Which task do you wish to kill?\n")
        print("(0) Exit")
        for process in process_list:
            if "date" in process:
                print(
                    "({}) {:<35}{:>20}".format(
                        process_list.index(process) + 1,
                        process["action"],
                        datetime.datetime.fromtimestamp(process["date"]).strftime(
                            "%b %d %H:%M:%S"
                        ),
                    )
                )
            else:
                print(
                    "({}) {:<35}".format(
                        process_list.index(process) + 1,
                        process["action"],
                    )
                )
        choise = read(min=0, max=len(process_list), digit=True)
        if choise == 0:
            return
        else:
            if isWindows:
                run("taskkill /F /PID {}".format(process_list[choise - 1]["pid"]))
            else:
                run("kill -9 {}".format(process_list[choise - 1]["pid"]))

def do_it(session: Session):
    ...
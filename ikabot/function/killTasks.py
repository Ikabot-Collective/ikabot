#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import json
import sys

from ikabot.config import *
from ikabot.helpers.decorators import configurator
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import enter, read
from ikabot.helpers.process import run, updateProcessList


def _print_process_rows(process_list):
    for idx, process in enumerate(process_list, start=1):
        if "date" in process and process["date"] is not None:
            print(
                "({}) {:<35}{:>20} {:>10}".format(
                    idx,
                    process["action"],
                    datetime.datetime.fromtimestamp(process["date"]).strftime(
                        "%b %d %H:%M:%S"
                    ),
                    process["pid"],
                )
            )
        else:
            print(
                "({}) {:<35} {:>10}".format(
                    idx,
                    process["action"],
                    process["pid"],
                )
            )


@configurator
def killTasks(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    try:
        while True:
            banner()
            process_list = updateProcessList(session)
            process_list = [
                process for process in process_list if process["action"] != "killTasks"
            ]
            if len(process_list) == 0:
                print("There are no tasks running")
                enter()
                event.set()
                return
            print("Which task do you wish to kill?\n")
            print("(0) Exit")
            _print_process_rows(process_list)
            print("\n(c) View task config")
            choise = read(
                min=0,
                max=len(process_list),
                digit=True,
                additionalValues=["c", "C"],
            )
            if choise == 0:
                event.set()
                return
            elif isinstance(choise, str) and choise.lower() == "c":
                banner()
                print("Which task's config do you wish to view?\n")
                print("(0) Back")
                _print_process_rows(process_list)
                cfg_choice = read(min=0, max=len(process_list), digit=True)
                if cfg_choice == 0:
                    continue
                target = process_list[cfg_choice - 1]
                banner()
                print(f"Task: {target['action']} (PID: {target['pid']})\n")
                cfg = target.get("config")
                if cfg is not None:
                    print(json.dumps(cfg, indent=2, ensure_ascii=False))
                    print("\nSingle-line JSON (--config):")
                    print(json.dumps(cfg, ensure_ascii=False))
                else:
                    print("No config dictionary available for this task.")
                enter()
            else:
                if isWindows:
                    run("taskkill /F /PID {}".format(process_list[choise - 1]["pid"]))
                else:
                    run("kill -9 {}".format(process_list[choise - 1]["pid"]))
    except KeyboardInterrupt:
        event.set()
        return

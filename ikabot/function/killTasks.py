#! /usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import json
import sys

from ikabot.config import *
from ikabot.helpers.decorators import configurator
from ikabot.helpers.gui import *
from ikabot.helpers.ipc import build_task_command, save_batch_file, save_task_config
from ikabot.helpers.pedirInfo import enter, read
from ikabot.helpers.process import run, updateProcessList


def _save_one_config(session, process):
    path = save_task_config(session, process)
    print("Saved the task config to:\n{}\n".format(path))
    print("Relaunch it with:")
    print(build_task_command(session, process, path))


def _save_all_configs(session, processes):
    path, saved, skipped = save_batch_file(session, processes, "all")
    if skipped:
        print("Skipped (no config available): {}".format(", ".join(skipped)))
    if path is None:
        print("Nothing to save.")
        return
    print("Saved {} task config(s) to:\n{}\n".format(saved, path))
    print("Relaunch them all with:")
    print('ikabot --batch="@{}"'.format(path))
    print("\nAdd --player=<name> (or --world / --email) to launch them on another account.")


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
            print("Running tasks. Enter a task's number to kill it.\n")
            print("(0) Exit")
            _print_process_rows(process_list)
            print("\n(c) View / save a task config")
            print("(a) Save all task configs to a file")
            choise = read(
                min=0,
                max=len(process_list),
                digit=True,
                additionalValues=["c", "C", "a", "A"],
            )
            if choise == 0:
                event.set()
                return
            elif isinstance(choise, str) and choise.lower() == "a":
                banner()
                _save_all_configs(session, process_list)
                enter()
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
                if cfg is None:
                    print("No config dictionary available for this task.")
                    enter()
                    continue
                print(json.dumps(cfg, indent=2, ensure_ascii=False))
                print("\nSingle-line JSON (--config):")
                print(json.dumps(cfg, ensure_ascii=False))
                print("\n(s) Save to a file to relaunch it from the command line")
                print("(Enter) Back")
                if str(read(values=["s", "S", ""])).lower() == "s":
                    _save_one_config(session, target)
                    enter()
            else:
                if isWindows:
                    run("taskkill /F /PID {}".format(process_list[choise - 1]["pid"]))
                else:
                    run("kill -9 {}".format(process_list[choise - 1]["pid"]))
    except KeyboardInterrupt:
        event.set()
        return

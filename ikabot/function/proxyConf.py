#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

import requests

import ikabot.config as config
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import read


def show_proxy(session):
    session_data = session.getSessionData()
    msg = "using proxy:"
    if "proxy" in session_data and session_data["proxy"]["set"] is True:
        curr_proxy = session_data["proxy"]["conf"]["https"]
        if test_proxy(session, session_data["proxy"]["conf"]) is False:
            session_data["proxy"]["set"] = False
            session.setSessionData(session_data)
            sys.exit(
                "the {} proxy does not work, it has been removed".format(curr_proxy)
            )
        if msg not in config.update_msg:
            # add proxy message
            config.update_msg += "{} {}\n".format(msg, curr_proxy)
        else:
            # delete old proxy message
            config.update_msg = config.update_msg.replace(
                "\n".join(config.update_msg.split("\n")[-2:]), ""
            )
            # add new proxy message
            config.update_msg += "{} {}\n".format(msg, curr_proxy)
    elif msg in config.update_msg:
        # delete old proxy message
        config.update_msg = config.update_msg.replace(
            "\n".join(config.update_msg.split("\n")[-2:]), ""
        )


def test_proxy(session, proxy_dict):
    try:
        requests.get(
            session.urlBase,
            proxies=proxy_dict,
            verify=config.do_ssl_verify,
        )
    except Exception as e:
        print('Proxy test failure. Error: ' + str(e))
        return False
    return True


def read_proxy(session):
    print(
        
        "Enter the proxy: protocol://username:password@address:port\n(examples: socks5://127.0.0.1:9050, https://45.117.163.22:8080):"
        
    )
    proxy_str = read(msg="proxy: ")
    proxy_dict = {"http": proxy_str, "https": proxy_str}
    if test_proxy(session, proxy_dict) is False:
        print("The proxy does not work.")
        enter()
        return None
    print("The proxy works and it will be used for all future requests sent by new ikabot processes.")
    enter()
    return proxy_dict


def proxyConf(session, event, stdin_fd, predetermined_input):
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
        banner()
        print(
            "Warning: The proxy does not apply to the requests sent to the lobby!\n"
        )

        session_data = session.getSessionData()
        if "proxy" not in session_data or session_data["proxy"]["set"] is False:
            print("Right now, there is no proxy configured.")
            proxy_dict = read_proxy(session)
            if proxy_dict is None:
                event.set()
                return
            session_data["proxy"] = {}
            session_data["proxy"]["conf"] = proxy_dict
            session_data["proxy"]["set"] = True
        else:
            curr_proxy = session_data["proxy"]["conf"]["https"]
            print("Current proxy: {}".format(curr_proxy))
            print("What do you want to do?")
            print("0) Exit")
            print("1) Set a new proxy")
            print("2) Remove the current proxy")
            rta = read(min=0, max=2)

            if rta == 0:
                event.set()
                return
            if rta == 1:
                proxy_dict = read_proxy(session)
                if proxy_dict is None:
                    event.set()
                    return
                session_data["proxy"]["conf"] = proxy_dict
                session_data["proxy"]["set"] = True
            if rta == 2:
                session_data["proxy"]["set"] = False
                print("The proxy has been removed.")
                enter()

        session.setSessionData(session_data)
        event.set()
    except KeyboardInterrupt:
        event.set()
        return
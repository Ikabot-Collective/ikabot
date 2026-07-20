#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import traceback

from requests import get, post

from ikabot.config import *
from ikabot.helpers.dns import getAddress


def getNewBlackBoxToken(session):
    """This function returns a newly generated blackbox token from the API
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object

    Returns
    -------
    token : str
        blackbox token
    """
    address = getAddress(publicAPIServerDomain) + "/v1/token"
    user_agent = getattr(session, "api_user_agent", None) or session.user_agent
    params = {
        "user_agent": user_agent,
        "locale": session.locale,
        "timezone_id": session.timezone_id,
    }
    response = get(
        address, params=params, verify=do_ssl_verify, timeout=900
    )
    if response.status_code in [400, 422]:
        fallback_params = {"user_agent": user_agent}
        response = get(
            address, params=fallback_params, verify=do_ssl_verify, timeout=900
        )
    assert response.status_code == 200, (
        "API response code is not OK: "
        + str(response.status_code)
        + "\n"
        + response.text
    )
    response = response.json()
    if isinstance(response, dict):
        if response.get("status") == "error":
            raise Exception(response["message"])
        raise Exception("Unexpected API response: " + str(response))
    return "tra:" + response.replace("tra:", "")


def getPiratesCaptchaSolution(session, image):
    """This function returns the solution of the pirates captcha
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    image : bytes
        the image to be solved

    Returns
    -------
    solution : str
        solution of the captcha
    """
    address = getAddress(publicAPIServerDomain) + "/v1/decaptcha/pirate"
    files = {"image": image}
    response = post(address, files=files, verify=do_ssl_verify, timeout=900)
    assert response.status_code == 200, (
        "API response code is not OK: "
        + str(response.status_code)
        + "\n"
        + response.text
    )
    response = response.json()
    if "status" in response and response["status"] == "error":
        raise Exception(response["message"])
    return response

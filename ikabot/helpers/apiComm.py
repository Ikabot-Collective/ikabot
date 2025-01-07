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
    address = (
        getAddress(publicAPIServerDomain)
        + "/v1/token"
        + "?user_agent="
        + session.user_agent
    )
    response = get(address, verify=do_ssl_verify, timeout=900)
    assert response.status_code == 200, (
        "API response code is not OK: "
        + str(response.status_code)
        + "\n"
        + response.text
    )
    response = response.json()
    if "status" in response and response["status"] == "error":
        raise Exception(response["message"])
    return "tra:" + response


def getInteractiveCaptchaSolution(session, text_image, icons_image):
    """This function returns the solution of the interactive captcha
    Parameters
    ----------
    session : ikabot.web.session.Session
        Session object
    icons_image : bytes
        the image that contains 4 other images
    text_image : bytes
        the image that contaisn the text

    Returns
    -------
    solution : str
        solution of the captcha
    """
    address = getAddress(publicAPIServerDomain) + "/v1/decaptcha/lobby"
    files = {"text_image": text_image, "icons_image": icons_image}
    response = post(address, files=files, verify=do_ssl_verify, timeout=900)
    assert response.status_code == 200, (
        "API response code is not OK: "
        + str(response.status_code)
        + "\n"
        + response.text
    )
    response = response.json()
    if type(response) is not int:
        raise Exception('Response was not a digit as expected: ' + response)
#    if "status" in response and response["status"] == "error":
#        raise Exception(response["message"])
    return response


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

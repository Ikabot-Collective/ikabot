import json
import os

import pytest
import requests

from ikabot.config import *
from ikabot.helpers.dns import getAddress


@pytest.fixture
def base_url():
    address = getAddress(domain=publicAPIServerDomain)
    return address + "/v1"


def test_decaptcha_without_data_should_return_status_code_400(base_url):
    response = requests.post(f"{base_url}/decaptcha/lobby")
    assert response.status_code == 400


def test_decaptcha_login_captcha_with_valid_image_should_return_the_right_int(base_url):
    current_directory = os.path.dirname(__file__)

    # Case 1
    file_path1 = os.path.join(current_directory, "img", "login_text1.png")
    file_path2 = os.path.join(current_directory, "img", "login_icons1.png")

    with open(file_path1, "rb") as text_image, open(file_path2, "rb") as icons_image:
        data = {
            "text_image": ("login_text1.png", text_image, "image/png"),
            "icons_image": ("login_icons1.png", icons_image, "image/png"),
        }
        response = requests.post(f"{base_url}/decaptcha/lobby", files=data)
    assert response.status_code == 200
    assert json.loads(response.text) == 3

    # Case 2
    file_path1 = os.path.join(current_directory, "img", "login_text2.png")
    file_path2 = os.path.join(current_directory, "img", "login_icons2.png")
    with open(file_path1, "rb") as text_image, open(file_path2, "rb") as icons_image:
        data = {
            "text_image": ("login_text2.png", text_image, "image/png"),
            "icons_image": ("login_icons2.png", icons_image, "image/png"),
        }
        response = requests.post(f"{base_url}/decaptcha/lobby", files=data)
    assert response.status_code == 200
    assert json.loads(response.text) == 0


def test_decaptcha_login_captcha_with_invalid_image_should_return_status_code_500(
    base_url,
):
    current_directory = os.path.dirname(__file__)

    file_path1 = os.path.join(current_directory, "img", "login_text_invalid.png")
    file_path2 = os.path.join(current_directory, "img", "login_icons_invalid.png")

    with open(file_path1, "rb") as text_image, open(file_path2, "rb") as icons_image:
        data = {
            "text_image": ("login_text_invalid.png", text_image, "image/png"),
            "icons_image": ("login_text_invalid.png", icons_image, "image/png"),
        }
        response = requests.post(f"{base_url}/decaptcha/lobby", files=data)
    assert response.status_code == 500

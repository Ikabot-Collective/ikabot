import os

import pytest
import requests

from ikabot.helpers.dns import getAddress
from ikabot.config import *


@pytest.fixture
def base_url():
    address = getAddress(domain = publicAPIServerDomain)
    # Remove "/ikagod/ikabot" from the URL
    base_url = f"http://{address}".replace("/ikagod/ikabot", "")
    return base_url


def test_decaptcha_without_data_should_return_error(base_url):
    response = requests.post(f"{base_url}/ikagod/ikabot")
    assert response.status_code == 200
    assert response.text == "Error"


def test_decaptcha_piracy_with_valid_image_should_return_the_right_string(base_url):
    current_directory = os.path.dirname(__file__)

    # Case 1
    file_path = os.path.join(current_directory, "img", "pirate1.png")
    with open(file_path, "rb") as f:
        data = {"upload_file": ("pirate1.png", f, "image/png")}
        response = requests.post(f"{base_url}/ikagod/ikabot", files=data)
    assert response.status_code == 200
    assert response.text == "QKB24JC"

    # Case 2
    file_path = os.path.join(current_directory, "img", "pirate2.png")
    with open(file_path, "rb") as f:
        data = {"upload_file": ("pirate2.png", f, "image/png")}
        response = requests.post(f"{base_url}/ikagod/ikabot", files=data)
    assert response.status_code == 200
    assert response.text == "DEVL5KA"


def test_decaptcha_piracy_with_invalid_size_should_return_error(base_url):
    current_directory = os.path.dirname(__file__)
    file_path = os.path.join(current_directory, "img", "pirate_invalid_size.png")
    with open(file_path, "rb") as f:
        data = {"upload_file": ("pirate_invalid_size.png", f, "image/png")}
        response = requests.post(f"{base_url}/ikagod/ikabot", files=data)
    assert response.status_code == 200
    assert response.text == "Error"


def test_decaptcha_login_captcha_with_valid_image_should_return_the_right_int(base_url):
    current_directory = os.path.dirname(__file__)

    # Case 1
    file_path1 = os.path.join(current_directory, "img", "login_text1.png")
    file_path2 = os.path.join(current_directory, "img", "login_icons1.png")

    with open(file_path1, "rb") as text_image, open(file_path2, "rb") as drag_icons:
        data = {
            "text_image": ("login_text1.png", text_image, "image/png"),
            "drag_icons": ("login_icons1.png", drag_icons, "image/png"),
        }
        response = requests.post(f"{base_url}/ikagod/ikabot", files=data)
    assert response.status_code == 200
    assert response.text == "3"

    # Case 2
    file_path1 = os.path.join(current_directory, "img", "login_text2.png")
    file_path2 = os.path.join(current_directory, "img", "login_icons2.png")

    with open(file_path1, "rb") as text_image, open(file_path2, "rb") as drag_icons:
        data = {
            "text_image": ("login_text2.png", text_image, "image/png"),
            "drag_icons": ("login_icons2.png", drag_icons, "image/png"),
        }
        response = requests.post(f"{base_url}/ikagod/ikabot", files=data)
    assert response.status_code == 200
    assert response.text == "0"


def test_decaptcha_login_captcha_with_invalid_image_should_return_error(
    base_url,
):
    current_directory = os.path.dirname(__file__)

    file_path1 = os.path.join(current_directory, "img", "login_text_invalid.png")
    file_path2 = os.path.join(current_directory, "img", "login_icons_invalid.png")

    with open(file_path1, "rb") as text_image, open(file_path2, "rb") as drag_icons:
        data = {
            "text_image": ("login_text_invalid.png", text_image, "image/png"),
            "drag_icons": ("login_text_invalid.png", drag_icons, "image/png"),
        }
        response = requests.post(f"{base_url}/ikagod/ikabot", files=data)

    assert response.status_code == 200
    assert response.text == "Error"

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
    response = requests.post(f"{base_url}/decaptcha/pirate")
    assert response.status_code == 400


def test_decaptcha_piracy_with_valid_image_should_return_the_right_string(base_url):
    current_directory = os.path.dirname(__file__)

    # Case 1
    file_path = os.path.join(current_directory, "img", "pirate1.png")
    with open(file_path, "rb") as f:
        data = {"image": ("pirate1.png", f, "image/png")}
        response = requests.post(f"{base_url}/decaptcha/pirate", files=data)
    assert response.status_code == 200
    assert json.loads(response.text) == "QKB24JC"

    # Case 2
    file_path = os.path.join(current_directory, "img", "pirate2.png")
    with open(file_path, "rb") as f:
        data = {"image": ("pirate2.png", f, "image/png")}
        response = requests.post(f"{base_url}/decaptcha/pirate", files=data)
    assert response.status_code == 200
    assert json.loads(response.text) == "DEVL5KA"


def test_decaptcha_piracy_with_invalid_size_should_return_status_code_500(base_url):
    current_directory = os.path.dirname(__file__)
    file_path = os.path.join(current_directory, "img", "pirate_invalid_size.png")
    with open(file_path, "rb") as f:
        data = {"image": ("pirate_invalid_size.png", f, "image/png")}
        response = requests.post(f"{base_url}/decaptcha/pirate", files=data)
    assert response.status_code == 500

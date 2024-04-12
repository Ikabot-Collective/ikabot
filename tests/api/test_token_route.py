import pytest
import requests

from ikabot.helpers.dns import getAddress
from ikabot.config import *


@pytest.fixture
def base_url():
    address = getAddress(domain = publicAPIServerDomain)
    # Remove "/ikagod/ikabot" from the URL
    base_url = address.replace("/ikagod/ikabot", "")
    return base_url


def test_get_token_should_return_status_code_ok(base_url):
    response = requests.get(f"{base_url}/token")
    assert response.status_code == 200

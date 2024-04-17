import pytest
import requests

from ikabot.config import *
from ikabot.helpers.dns import getAddress

valid_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.2"


@pytest.fixture
def base_url():
    address = getAddress(domain=publicAPIServerDomain)
    return address + "/v1"


def test_get_token_should_return_status_code_ok(base_url):
    response = requests.get(f"{base_url}/token?user_agent=" + valid_user_agent)
    assert response.status_code == 200

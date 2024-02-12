import pytest
import requests

from ikabot.helpers.process import run


@pytest.fixture
def base_url():
    text = run("nslookup -q=txt ikagod.twilightparadox.com ns2.afraid.org")
    parts = text.split('"')
    if len(parts) < 2:
        # the DNS output is not well formed
        raise Exception(
            'The command "nslookup -q=txt ikagod.twilightparadox.com ns2.afraid.org" returned bad data: {}'.format(
                text
            )
        )
    address = parts[1]
    # Remove "/ikagod/ikabot" from the URL
    base_url = f"http://{address}".replace("/ikagod/ikabot", "")
    return base_url


def test_get_token_should_return_status_code_ok(base_url):
    response = requests.get(f"{base_url}/token")
    assert response.status_code == 200

from ikabot.helpers.dns import getAddress
import os
import sys

def developer(session, event, stdin_fd, *args):
    sys.stdin = os.fdopen(stdin_fd)
    print("\n=== Developer Information ===\n")

    # Ikabot public API address (blackbox / decaptcha etc)
    try:
        api_address = getAddress()
    except Exception:
        api_address = "Could not resolve"

    print("Ikabot API address:", api_address)
    print("CUSTOM_API_ADDRESS:", os.getenv("CUSTOM_API_ADDRESS"))

    print("\nGame host:", getattr(session, "host", "Not available"))
    print("Game URL base:", getattr(session, "urlBase", "Not available"))

    cookies = session.s.cookies.get_dict()
    print("\nCookies:")
    print("ikariam:", cookies.get("ikariam", "Not set"))
    print("gf-token-production:", cookies.get("gf-token-production", "Not set"))
    input("\nPress enter to return...")
    event.set()
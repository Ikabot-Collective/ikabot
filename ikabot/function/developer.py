from ikabot.helpers.dns import getAddress
import ikabot
import os
import sys

def developer(session, event, stdin_fd, *args):
    sys.stdin = os.fdopen(stdin_fd)
    print("\n=== Developer Information ===\n")

    # 1. Get the ikabot package directory
    try:
        ikabot_dir = os.path.dirname(ikabot.__file__)
    except Exception as e:
        ikabot_dir = f"Error locating package: {e}"

    # 2. Ikabot public API address (blackbox / decaptcha etc)
    try:
        api_address = getAddress()
    except Exception as e:
        api_address = f"Could not resolve: {e}"

    print(f"Ikabot Install Directory: {ikabot_dir}")
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

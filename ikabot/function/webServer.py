#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from ikabot.helpers.logging import getLogger
import base64
import json
import pickle
import re
import socket
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import unquote_plus, unquote

import requests

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import *
from ikabot.helpers.gui import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.process import run, set_child_mode, updateProcessList
from ikabot.helpers.varios import wait


class ResponseTypes:
    SUCCESS = 10
    FAILURE = 11
    WARNING = 12
    GREEN = 10
    RED = 11
    YELLOW = 12

if isWindows:
    web_cache_file = os.getenv("temp") + "/ikabot.webcache"
else:
    web_cache_file = "/tmp/ikabot.webcache"


def webServer(session, event, stdin_fd, predetermined_input, port=None):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    port : int (optional)
    """
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input

    banner()
    try:
        import flask
        from flask import Flask, Response, request
    except Exception:
        print(
            "You must have flask installed for this feature to work. Do you want to install it now?[Y/N]"
        )
        choice = read(values=["y", "Y", "n", "N"])
        if choice in ["y", "Y"]:
            print(
                f"Attempting to install flask... -> {bcolors.GREEN}python3 -m pip install flask{bcolors.ENDC}"
            )
            command_output = run("python3 -m pip install flask")
            print(command_output)
        else:
            print("Please install flask manually and try to run this module again...")
            enter()
            event.set()
            return
        try:
            import flask
            from flask import Flask, Response, request
        except Exception:
            print(
                "Failed to install flask. Please install it manually and try to run this module again..."
            )
            enter()
            event.set()
            return

    sys.flask = flask

    web_cache = dict()
    # check if webcache already exists and load it if it does
    try:
        if os.path.isfile(web_cache_file):
            with open(web_cache_file, "rb") as f:
                web_cache = pickle.load(f)
        else:
            with open(web_cache_file, "wb") as f:
                pickle.dump(web_cache, f)
    except: pass # TODO add warning about failing to open webcache file

    def dump_cache():
        while True:
            time.sleep(300)
            try:
                with open(web_cache_file, "wb") as f:
                    pickle.dump(web_cache, f)
            except: pass

    # dump cache in a separate thread every 5 minutes
    threading.Thread(target=dump_cache, daemon=True).start()

    import flask.cli
    flask.cli.show_server_banner = lambda *args: None

    try:
        app = Flask("Ikabot web server")
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        app.logger = getLogger(__name__)
        app.logger.setLevel(logging.ERROR)

        @app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
        @app.route("/<path:path>", methods=["GET", "POST"])
        def webServer(path):

            dest_url = f"{path}"
            
            if "ikabot=1" in request.url:
                return handleIkabotAPIRequest(session, request)

            # replace mayor
            if "/cdn/all/both/layout/advisors/mayor" in request.url:
                image_data = (
                    base64.b64decode(woke_mayor)
                    if "active" not in request.url
                    else base64.b64decode(woke_mayor_active)
                )
                # Convert the bytes data to a BytesIO object that Flask can send
                image_io = BytesIO(image_data)
                image_io.seek(0)
                expires = datetime.utcnow() + timedelta(days=1)
                headers = dict()
                headers["Expires"] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
                headers["Cache-Control"] = "public, max-age=86400"
                response = Response(image_io, 200, headers)
                return response

            if (
                ".png" in request.url
                or ".jpg" in request.url
                or ".gif" in request.url
                or ".cur" in request.url
            ):
                # add caching for images
                expires = datetime.utcnow() + timedelta(days=1)
                headers = dict()
                headers["Expires"] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
                headers["Cache-Control"] = "public, max-age=86400"
                name = request.url.split("/")[-1]
                if name in web_cache:
                    return Response(BytesIO(web_cache[name]), 200, headers)

            new_data = dict()
            try:
                data = request.get_data(as_text=True)
                data = unquote(data, encoding='utf-8', errors='replace')
                if data:
                    for item in data.split("&"):
                        k, v = item.split("=")
                        new_data[k] = unquote_plus(v)
            except Exception:
                pass
            for arg in request.args:
                new_data[arg] = unquote_plus(request.args[arg])
            for arg in new_data:
                if arg == "actionRequest":
                    new_data[arg] = (
                        actionRequest  # this is to prevent custom requests from going to ikariam servers
                    )
                if arg == "view" and new_data[arg] == "ikabotSandbox":
                    new_data[arg] = "version"
                if arg == "activeTab" and new_data[arg] == "tab_ikabotSandbox":
                    new_data[arg] = "tab_version"
            if request.method in ["POST"]:
                resp = session.post(
                    dest_url,
                    params=new_data,
                    noIndex=True,
                    fullResponse=True,
                    noQuery=True,
                    allow_redirects=False,
                )
            else:
                resp = session.get(
                    dest_url,
                    params=new_data,
                    noIndex=True,
                    fullResponse=True,
                    noQuery=True,
                    allow_redirects=False,
                )

            if (
                ".png" in request.url
                or ".jpg" in request.url
                or ".gif" in request.url
                or ".cur" in request.url
            ):
                # cache was missed, add to cache and send response
                expires = datetime.utcnow() + timedelta(days=1)
                headers = dict()
                headers["Expires"] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
                headers["Cache-Control"] = "public, max-age=86400"
                response = Response(resp.content, 200, headers)
                web_cache[request.url.split("/")[-1]] = resp.content
                return response

            # Replace all instances of the target URL with the proxy URL
            # modified_content = resp.text.replace(session.urlBase.replace( '/index.php?', ''), 'http://localhost:589').replace(session.host, 'localhost:589')

            modified_content = resp.text

            # prevent losing reference to console object. sneaky gameforge...
            modified_content = modified_content.replace("console = ", "")

            # use regex to replace the script with id="cookiebanner" with custom script
            scripts = re.findall(r"(<script[\S\s]*?script>)", modified_content)
            for script in scripts:
                if "cookiebanner" in script:
                    modified_content = modified_content.replace(script, custom_script)
                if "log: function" in script or "dir: function" in script:
                    modified_content = modified_content.replace(script, "")

            # intercept and modify response to version request, add sandbox html
            if (
                "view=version" in request.url
                or "view=normalServerStatus" in request.url
                or "view=ikabotSandbox" in request.url
            ):
                return addSandbox(session, resp, request)

            # Create a new response with the modified content
            proxied_response = Response(modified_content, status=resp.status_code) if modified_content[1:4] != "PNG" else Response(resp.content, status=resp.status_code, content_type="image/png")

            # Copy over headers
            excluded_headers = [
                "content-encoding",
                "content-length",
                "transfer-encoding",
                "connection",
            ]
            for header in resp.headers:
                if header.lower() not in excluded_headers:
                    proxied_response.headers[header] = resp.headers[header]

            return proxied_response

        def is_port_in_use(port: int) -> bool:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    return s.connect_ex(("127.0.0.1", port)) == 0
            except Exception as e:
                logger.log(
                    logging.FATAL,
                    f"Error while checking if port {str(port)} is in use: " + str(e),
                )
                raise e

        # If the port is not provided, prompt the user for it if enabled from the config file
        if config.enable_CustomPort is True:
            while True:
                if port is None:
                    print("Please enter a port number (1 - 65535) to run the web server on (leave empty or 0 for random): ")
                    port = read(min=0, max=65535, digit=True, empty=True)
                    if port == "" or port == 0:
                        port = None
                        break
                    else:
                        port = str(int(port))
                        if is_port_in_use(int(port)):
                            print(f"Port {port} is already in use, try another port.")
                            continue
                        break

        # If the port is still None, select a random port as in the original script
        if port is None:
            port = str(
                (
                    sum(ord(c) ** 2 for c in session.mail)
                    + sum(ord(c) ** 2 for c in session.host)
                    + sum(ord(c) ** 2 for c in session.username)
                )
                % 2000
                + 43000
            )

            # bang on ports from `port` to 65535 until an available one is found
            while True:
                if not is_port_in_use(int(port)):
                    break
                port = str(int(port) + 1)

        # try to get local network ip if possible
        local_network_ip = None
        try:
            local_network_ip = socket.gethostbyname(socket.gethostname())
        except:
            pass
        print(
            f"""Ikabot web server is about to be run on {bcolors.BLUE}http://127.0.0.1:{port}{bcolors.ENDC} {'and ' + bcolors.BLUE + 'http://' + str(local_network_ip) + ':' + port + bcolors.ENDC if local_network_ip else ''}"""
        )
        print(
            "You can use this link in your browser to play ikariam without logging ikabot out."
        )
        print(
            "If you wish to access this ikabot web server from another device that is not on this local network"
        )
        print(
            "you can try to run one of the following commands in a separate terminal and use the link that it provides to connect:"
        )
        print(
            f"{bcolors.DARK_GREEN}ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:{port} serveo.net{bcolors.ENDC}"
        )
        print("Or you can try:")
        print(
            f"{bcolors.DARK_GREEN}ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:{port} nokey@localhost.run{bcolors.ENDC}"
        )

        print(
            f"\n        {bcolors.WARNING}[WARNING]{bcolors.ENDC} Make sure you don't share this link with anyone you don't trust!"
        )

        print(
            "\nPress [ENTER] if you want to run the web server now, or CTRL+C to go back to the main menu"
        )
        enter()
        session.setStatus(
            f"""running on http://127.0.0.1:{port} {'and '+'http://' + str(local_network_ip) + ':' + port if local_network_ip else ''}"""
        )
        event.set()
        app.run(host="0.0.0.0", port=int(port), threaded=True)

    except Exception:
        event.set()
        return


def handleIkabotAPIRequest(session, request):
    if request.args["action"] == "killTask":
        try:
            if isWindows:
                run(f"taskkill /F /PID {request.args['pid']}")
            else:
                run(f"kill -9 {request.args['pid']}")
            return mayorMessageResponse(
                ResponseTypes.SUCCESS, "Task successfully killed!"
            )
        except:
            return mayorMessageResponse(ResponseTypes.FAILURE, "Failed to kill task!")


def mayorMessageResponse(type: ResponseTypes, message: str):
    return f"""[["provideFeedback",[{{"location":1,"type":{type},"text":"[IKABOT] {message}"}}]]]"""


def addSandbox(session, resp, req):

    json_result = resp.json()

    html = json_result[1][1][1]

    # replace tab menu with custom tab menu
    if "view=version" in req.url:
        html = re.sub(r"<ul class=\"tabmenu\"[\S\s]*?<\/ul>", tab_menu, html)
    elif "view=normalServerStatus" in req.url:
        html = re.sub(
            r"<ul class=\"tabmenu\"[\S\s]*?<\/ul>",
            tab_menu.replace("selected", "").replace(
                'normalServerStatus" class="tab "',
                'normalServerStatus" class="tab selected"',
            ),
            html,
        )
    elif "view=ikabotSandbox" in req.url:
        html = re.sub(
            r"<ul class=\"tabmenu\"[\S\s]*?<\/ul>",
            tab_menu.replace("selected", "").replace(
                'ikabotSandbox" class="tab "', 'ikabotSandbox" class="tab selected"'
            ),
            html,
        )

    if "view=ikabotSandbox" in req.url:
        # build process table html
        process_list = updateProcessList(session)
        table_html = generateTableHTML(process_list)
        html = sandbox_html.replace("TABLE_HTML", table_html)
        # build proxy string html
        proxy_data = session.getSessionData().get("proxy")
        if proxy_data and "conf" in proxy_data and proxy_data["set"] is True:
            html = html.replace(
                "PROXY_DATA",
                f"""<div style="margin-left:2%;"><b>Proxy:</b> {proxy_data['conf']['https']}</div>""",
            )
        else:
            html = html.replace(
                "PROXY_DATA",
                """<div style="margin-left:2%;"><b>Proxy:</b> No proxy set.</div>""",
            )

    json_result[1][1][1] = html

    return sys.flask.Response(
        json.dumps(json_result), 200, {"Content-Type": "text/html"}
    )


def generateTableHTML(process_list):
    table_html = """
        <table class="table01">
            <tr>
                <th>Pid</th>
                <th>Task</th>
                <th>Date</th>
                <th>Status</th>
                <th>Kill</th>
            </tr>
        """
    i = 0
    for process in process_list:
        tr_string = "<tr>"
        if i % 2 == 0:
            tr_string = '<tr class="alt">'
        table_html += f"{tr_string}\
            <td>{process['pid']}</td>\
            <td>{process['action']}</td>\
            <td>{datetime.fromtimestamp(process['date']).strftime('%Y-%m-%d %H:%M:%S')}</td>\
            <td style=\"font-size:0.8em\">{process['status']}</td>\
            <td><button class=\"button\" onclick=\"ajaxHandlerCall('?action=killTask&pid={process['pid']}&ikabot=1'); ajaxHandlerCall('?           view=ikabotSandbox&activeTab=tab_ikabotSandbox');\">Kill</button></td>\
            </tr>"
        i += 1

    table_html += "</table>"
    return table_html


# use double curly brackets for custom script because it's an fstring
custom_script = f"""
<script> 

window.onload = function() {{

    // get span element with title "Version" and replace it's text with current version
    var versionSpan = document.querySelector('span[title="Version"]');
    versionSpan.innerHTML = 'Ikabot {IKABOT_VERSION_TAG}';
    versionSpan.style = 'animation: glow 1s ease-in-out infinite alternate;';
    

    //NEWS


}}
</script>
<style>
@-webkit-keyframes glow {{
  from {{
    text-shadow: 0 0 2px #ff3d00, 0 0 6px #ff3d00;
  }}
  
  to {{
    text-shadow: 0 0 16px #ff3d00, 0 0 12px #ff3d00;
  }}
}}

</style>
"""

tab_menu = """
<ul class="tabmenu">
        <li onclick="ajaxHandlerCall('?view=version&activeTab=tab_version'); return false;" id="js_tab_version"
            class="tab  selected"><b class="tab_version">ChangeLog</b>
        </li>
        <li onclick="ajaxHandlerCall('?view=normalServerStatus&activeTab=tab_normalServerStatus'); return false;"
            id="js_tab_normalServerStatus" class="tab "><b class="tab_normalServerStatus">World info</b>
        </li>
        <li onclick="ajaxHandlerCall('?view=ikabotSandbox&activeTab=tab_ikabotSandbox'); return false;"
            id="js_tab_ikabotSandbox" class="tab "><b class="tab_ikabotSandbox">Ikabot</b>
        </li>
</ul>

"""

sandbox_html = """
<div id="mainview">
    <div class="buildingDescription heightLessBuildingDescription">
        <h1>Ikabot</h1>
    </div>


    <ul class="tabmenu">
        <li onclick="ajaxHandlerCall('?view=version&activeTab=tab_version'); return false;" id="js_tab_version"
            class="tab  "><b class="tab_version">ChangeLog</b>
        </li>
        <li onclick="ajaxHandlerCall('?view=normalServerStatus&activeTab=tab_normalServerStatus'); return false;"
            id="js_tab_normalServerStatus" class="tab "><b class="tab_normalServerStatus">World info</b>
        </li>
        <li onclick="ajaxHandlerCall('?view=ikabotSandbox&activeTab=tab_ikabotSandbox'); return false;"
            id="js_tab_ikabotSandbox" class="tab selected"><b class="tab_ikabotSandbox">Ikabot</b>
        </li>
    </ul>


    <div class="contentBox01h">
        <div class="header"></div>
        <div class="content">

            TABLE_HTML  

            PROXY_DATA    
            
            
        </div>
        <div class="footer"></div>
    </div>
</div>

"""


woke_mayor = "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"

woke_mayor_active = "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"

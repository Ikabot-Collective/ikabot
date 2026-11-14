"""Pirate Fortress building model (`view=pirateFortress`, `buildingId=30`)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import (
    AjaxResponse,
    format_feedback,
    has_feedback_error,
    parse_int,
    parse_query_int,
    parse_query_params,
)
from ikabot.ikariam.buildings._base import (
    Building,
    parse_duration_seconds,
    parse_view_payload,
    strip_hidden_text,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import IkariamClient


class CaptchaRequiredError(RuntimeError):
    """Raised when an action receives a Pirate Fortress CAPTCHA challenge."""

    def __init__(self, message: str, *, ajax_response: Optional[AjaxResponse] = None) -> None:
        super().__init__(message)
        self.ajax_response = ajax_response


_CAPTCHA_MARKERS = ("function=createCaptcha", "js_captchaImage")


def _response_has_captcha(resp: Optional[AjaxResponse]) -> bool:
    """Return ``True`` when an AJAX response carries a Pirate Fortress CAPTCHA challenge."""
    if resp is None:
        return False
    haystacks = [resp.view_html or "", json.dumps(resp.commands, ensure_ascii=False)]
    return any(marker in blob for blob in haystacks for marker in _CAPTCHA_MARKERS)


def _raise_if_captcha(resp: Optional[AjaxResponse]) -> None:
    """Abort without solving when a CAPTCHA challenge appears."""
    if _response_has_captcha(resp):
        raise CaptchaRequiredError(
            "Pirate Fortress requested a CAPTCHA challenge; manual completion is required.",
            ajax_response=resp,
        )


async def execute_piracy_raid(
    client: "IkariamClient",
    target_city_id: int,
    *,
    origin_city_id: Optional[int] = None,
    current_island_id: Optional[int] = None,
    action_name: str = "PirateFortress.raidCity",
) -> AjaxResponse:
    """Open ``view=piracyRaid`` for ``target_city_id`` and execute its raid link."""
    from ikabot.ikariam.city import _select_city_id
    from ikabot.ikariam.client import IkariamActionError

    if origin_city_id is not None:
        await _select_city_id(client, int(origin_city_id), action_name=action_name)

    params: Dict[str, str] = {
        "view": "piracyRaid",
        "destinationCityId": str(int(target_city_id)),
        "templateView": "piracyRaid",
        "actionRequest": "REQUESTID",
        "ajax": "1",
    }
    if current_island_id is not None:
        params["backgroundView"] = "island"
        params["currentIslandId"] = str(int(current_island_id))
    else:
        cur_id = origin_city_id or (
            client.selectedDropDownCity.id if client.selectedDropDownCity is not None else None
        )
        params["backgroundView"] = "city"
        if cur_id is not None:
            params["currentCityId"] = str(cur_id)

    view_resp = await client.post_ajax(params=params)
    _raise_if_captcha(view_resp)
    if has_feedback_error(view_resp.feedback) or not view_resp.view_html:
        detail = format_feedback(view_resp.feedback) or "missing piracyRaid view"
        raise ValueError(f"Could not open piracyRaid for city {target_city_id}: {detail}")

    soup = BeautifulSoup(view_resp.view_html, "html.parser")
    action_link = soup.select_one("#actionLink")
    href = str(action_link.get("href") or "") if action_link is not None else ""
    classes = set(action_link.get("class") or []) if action_link is not None else set()
    if not href or "button_disabled" in classes or "disabled" in classes:
        detail = format_feedback(view_resp.feedback) or "raid action link unavailable"
        raise ValueError(f"Cannot raid city {target_city_id}: {detail}")

    raid_params = parse_query_params(href)
    raid_params.setdefault("action", "PiracyScreen")
    raid_params.setdefault("function", "raid")
    raid_params.setdefault("destinationCityId", str(int(target_city_id)))
    raid_params["backgroundView"] = params["backgroundView"]
    if "currentIslandId" in params:
        raid_params["currentIslandId"] = params["currentIslandId"]
    elif "currentCityId" in params:
        raid_params["currentCityId"] = params["currentCityId"]
    raid_params["templateView"] = "piracyRaid"
    raid_params["actionRequest"] = "REQUESTID"

    try:
        raid_resp = await client.post_action(
            params=raid_params,
            metadata={"ambrosia_cost": 0, "targetCityId": int(target_city_id)},
            action_name=action_name,
        )
    except IkariamActionError as exc:
        _raise_if_captcha(exc.ajax_response)
        raise
    _raise_if_captcha(raid_resp)
    return raid_resp


_AVAILABLE_LEVEL_RE = re.compile(r"Available\s+from\s+level\s+(\d+)", re.IGNORECASE)
_CITY_ID_ONCLICK_RE = re.compile(r"cityId=(\d+)")
_SWITCH_TAB_RE = re.compile(r'switchTab\(["\']([^"\']+)["\']\)')
_WS_RE = re.compile(r"\s+")


def _clean_text(value: Any) -> str:
    """Collapse internal whitespace cleanly."""
    return _WS_RE.sub(" ", str(value or "")).strip()


def _parse_load_js_params(resp: AjaxResponse) -> Dict[str, Any]:
    """Extract parsed JSON dict from ``resp.template_data['load_js']['params']``."""
    tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
    load_js = tmpl.get("load_js")
    if not isinstance(load_js, dict):
        return {}
    raw_params = load_js.get("params")
    if isinstance(raw_params, dict):
        return raw_params
    if not isinstance(raw_params, str) or not raw_params.strip():
        return {}
    try:
        parsed = json.loads(raw_params, strict=False)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass
class PirateCaptureLevel:
    """Capture-run mission tier inside ``#tabBootyQuest``."""

    requiredLevel: int
    name: str = ""
    durationSeconds: Optional[int] = None
    goldReward: int = 0
    capturePointsReward: int = 0
    canStart: bool = False
    actionUrl: Optional[str] = None
    availabilityText: str = ""


@dataclass
class PirateHighscoreEntry:
    """Entry in the Pirate Fortress mini-highscore ticker."""

    place: Optional[int] = None
    avatarId: Optional[int] = None
    name: str = ""
    capturePoints: int = 0
    cityId: Optional[int] = None
    islandId: Optional[int] = None
    distance: Optional[int] = None
    isSelf: bool = False


class PirateFortress(Building):
    """Ikariam Pirate Fortress model (``view=pirateFortress``).

    Both ``#tabBootyQuest`` and ``#tabCrew`` are rendered inline inside the
    primary response, enriched with ``load_js.params`` JSON when available.
    """

    buildingId: int = 30
    buildingType: str = "pirateFortress"

    def __init__(
        self,
        client: Optional["IkariamClient"] = None,
        city: Optional["City"] = None,
        cityId: Optional[int] = None,
        position: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        self.activeTab: str = "tabBootyQuest"
        self.capturePoints: int = 0
        self.crewStrength: int = 0
        self.basicCrewStrength: int = 0
        self.convertedCrewStrength: int = 0
        self.bonusCrewStrength: int = 0
        self.highscorePosition: Optional[int] = None
        self.highscorePlayerIndex: Optional[int] = None
        self.highscoreTimeLeftSeconds: Optional[int] = None
        self.highscoreTimeLeftText: str = ""
        self.highscore: List[PirateHighscoreEntry] = []
        self.nextLevelBonus: str = ""
        self.hasOngoingMission: bool = False
        self.hasOngoingConversion: bool = False
        self.captureLevels: List[PirateCaptureLevel] = []
        # Crew conversion (#tabCrew)
        self.crewConversionCost: int = 10
        self.crewConversionTimeBaseSeconds: Optional[int] = None
        self.crewConversionTimePerUnitSeconds: Optional[int] = None
        self.canConvertCrew: bool = False
        self._crew_form_inputs: Dict[str, str] = {}

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse header summary, highscore strip, capture runs, and crew tab."""
        params = _parse_load_js_params(resp)
        for script in soup.select("#mainview script"):
            m = _SWITCH_TAB_RE.search(script.get_text(" "))
            if m:
                self.activeTab = m.group(1)
                break

        self._parse_sidebar(soup, resp)
        self._parse_header_and_highscore(soup, resp, params)
        self._parse_booty_quest_dom(soup, params)
        self._parse_crew_dom(soup, params)

    def _parse_sidebar(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse next-level raid/crew bonus text from `#informationSidebar`."""
        info = soup.select_one("#informationSidebar p")
        if info is not None:
            self.nextLevelBonus = _clean_text(info.get_text(" ", strip=True))
            return
        tmpl = resp.template_data if isinstance(resp.template_data, dict) else {}
        nxt = tmpl.get("nextLevel")
        if isinstance(nxt, dict) and nxt.get("text"):
            self.nextLevelBonus = _clean_text(nxt.get("text"))

    def _parse_header_and_highscore(
        self,
        soup: BeautifulSoup,
        resp: AjaxResponse,
        params: Dict[str, Any],
    ) -> None:
        """Parse capture points, crew strength breakdown, timer, and highscore."""
        header = soup.select_one(".pirateHeader")
        if header is not None:
            cp_el = header.select_one("li.capturePoints .value")
            cp_val = parse_int(cp_el.get_text(" ", strip=True)) if cp_el else None
            if cp_val is not None:
                self.capturePoints = cp_val

            crew_el = header.select_one("li.pirateCrew > span.value")
            crew_val = parse_int(crew_el.get_text(" ", strip=True)) if crew_el else None
            if crew_val is not None:
                self.crewStrength = crew_val

            for tr in header.select(".breakdown_table tr"):
                desc_td = tr.select_one("td.description")
                val_td = tr.select_one("td.value")
                if desc_td is None or val_td is None:
                    continue
                label = _clean_text(desc_td.get_text(" ", strip=True)).lower()
                val = parse_int(val_td.get_text(" ", strip=True))
                if val is None:
                    continue
                if "basic crew" in label:
                    self.basicCrewStrength = val
                elif "crew strength bonus" in label:
                    self.bonusCrewStrength = val
                elif label.startswith("crew strength"):
                    self.convertedCrewStrength = val

            time_el = header.select_one("#piracyHighscoreTime")
            if time_el is not None:
                time_txt = _clean_text(time_el.get_text(" ", strip=True))
                self.highscoreTimeLeftText = time_txt
                self.highscoreTimeLeftSeconds = parse_duration_seconds(time_txt)

        # Prefer authoritative JSON values when load_js.params is present.
        if params:
            if (v := parse_int(params.get("capturePoints"))) is not None:
                self.capturePoints = v
            if (v := parse_int(params.get("completeCrewPoints"))) is not None:
                self.crewStrength = v
            if (v := parse_int(params.get("basicCrewPoints"))) is not None:
                self.basicCrewStrength = v
            if (v := parse_int(params.get("crewPoints"))) is not None:
                self.convertedCrewStrength = v
            if (v := parse_int(params.get("bonusCrewPoints"))) is not None:
                self.bonusCrewStrength = v
            if (v := parse_int(params.get("highscoreTimeLeft"))) is not None:
                self.highscoreTimeLeftSeconds = v
            self.highscorePlayerIndex = parse_int(params.get("highscorePlayerPosition"))
            self.hasOngoingMission = bool(params.get("hasOngoingMission", False))
            self.hasOngoingConversion = bool(
                params.get("hasOngoingConvertion", params.get("hasOngoingConversion", False))
            )

        self.highscore = self._parse_highscore_entries(soup, params)
        self.highscorePosition = None
        for entry in self.highscore:
            if entry.isSelf and entry.place is not None:
                self.highscorePosition = entry.place
                break
        if (
            self.highscorePosition is None
            and self.highscorePlayerIndex is not None
            and 0 <= self.highscorePlayerIndex < len(self.highscore)
        ):
            self.highscorePosition = self.highscore[self.highscorePlayerIndex].place

    def _parse_highscore_entries(
        self,
        soup: BeautifulSoup,
        params: Dict[str, Any],
    ) -> List[PirateHighscoreEntry]:
        """Parse Pirate Highscore strip from HTML and/or ``load_js.params['highscore']``."""
        js_rows: Dict[int, Dict[str, Any]] = {}
        raw_js_hs = params.get("highscore")
        if isinstance(raw_js_hs, list):
            for idx, item in enumerate(raw_js_hs):
                if isinstance(item, dict):
                    place = parse_int(item.get("place") or item.get("position") or item.get("rank"))
                    key = place if place is not None else idx
                    js_rows[key] = item

        entries: List[PirateHighscoreEntry] = []
        player_pos_idx = parse_int(params.get("highscorePlayerPosition"))
        for idx, li in enumerate(soup.select("#pirateHighscore > li")):
            place_el = li.select_one(".place")
            booty_el = li.select_one(".pirateBooty")
            name_el = li.select_one(".userName")
            place = parse_int(place_el.get_text(" ", strip=True)) if place_el else None
            cp = parse_int(booty_el.get_text(" ", strip=True)) if booty_el else 0
            name = _clean_text(name_el.get_text(" ", strip=True)) if name_el else ""
            if not name:
                span_titled = li.select_one("span[title]")
                if span_titled is not None:
                    name = _clean_text(span_titled.get("title"))

            city_id: Optional[int] = None
            onclick_a = li.select_one("a[onclick]")
            if onclick_a is not None:
                m_cid = _CITY_ID_ONCLICK_RE.search(str(onclick_a.get("onclick", "")))
                if m_cid:
                    city_id = int(m_cid.group(1))

            is_self = "player" in (li.get("class") or []) or (
                player_pos_idx is not None and idx == player_pos_idx
            )
            extra = js_rows.get(place) if place is not None else None
            avatar_id = parse_int(extra.get("avatarId")) if extra else None
            island_id = (parse_int(extra.get("islandId")) or None) if extra else None
            distance = parse_int(extra.get("distance")) if extra else None
            if city_id is None and extra:
                city_id = parse_int(extra.get("cityId")) or None

            entries.append(
                PirateHighscoreEntry(
                    place=place,
                    avatarId=avatar_id,
                    name=name,
                    capturePoints=cp if cp is not None else 0,
                    cityId=city_id,
                    islandId=island_id,
                    distance=distance,
                    isSelf=is_self,
                )
            )

        if not entries and isinstance(raw_js_hs, list):
            for idx, item in enumerate(raw_js_hs):
                if not isinstance(item, dict):
                    continue
                place = parse_int(item.get("place") or item.get("position") or item.get("rank"))
                entries.append(
                    PirateHighscoreEntry(
                        place=place,
                        avatarId=parse_int(item.get("avatarId")),
                        name=_clean_text(item.get("name") or item.get("playerName")),
                        capturePoints=parse_int(item.get("capturePoints") or item.get("points")) or 0,
                        cityId=parse_int(item.get("cityId")) or None,
                        islandId=parse_int(item.get("islandId")) or None,
                        distance=parse_int(item.get("distance")),
                        isSelf=(player_pos_idx is not None and idx == player_pos_idx),
                    )
                )

        return entries

    def _parse_booty_quest_dom(self, soup: BeautifulSoup, params: Dict[str, Any]) -> None:
        """Parse `#tabBootyQuest` mission rows enriched by `pirateCaptureLevels`."""
        js_levels: List[Dict[str, Any]] = []
        raw_levels = params.get("pirateCaptureLevels")
        if isinstance(raw_levels, list):
            js_levels = [lvl for lvl in raw_levels if isinstance(lvl, dict)]

        levels: List[PirateCaptureLevel] = []
        rows = soup.select("#pirateCaptureBox tbody tr")
        for idx, tr in enumerate(rows):
            tds = tr.select("td")
            if len(tds) < 5:
                continue

            name = _clean_text(tds[1].get_text(" ", strip=True))
            time_li = tr.select_one("td.requirement li.time")
            duration_s = parse_duration_seconds(
                strip_hidden_text(time_li, ("accesshint", "tooltip", "textLabel"))
                if time_li is not None
                else ""
            )

            gold_li = tr.select_one("td.reward li.gold")
            cp_li = tr.select_one("td.reward li.capturePoints")
            gold = (
                parse_int(
                    strip_hidden_text(gold_li, ("accesshint", "tooltip", "textLabel"))
                )
                if gold_li is not None
                else 0
            )
            cp = (
                parse_int(
                    strip_hidden_text(cp_li, ("accesshint", "tooltip", "textLabel"))
                )
                if cp_li is not None
                else 0
            )

            action_btn = tr.select_one("td.action a.button[href]")
            action_url = action_btn.get("href") if action_btn else None
            can_start = action_btn is not None and "button_disabled" not in (
                action_btn.get("class") or []
            )
            avail_text = _clean_text(tds[4].get_text(" ", strip=True))

            req_level = parse_query_int(action_url, "buildingLevel")
            if req_level is None:
                m_lvl = _AVAILABLE_LEVEL_RE.search(avail_text)
                if m_lvl:
                    req_level = int(m_lvl.group(1))

            if idx < len(js_levels):
                js_lvl = js_levels[idx]
                if req_level is None:
                    req_level = parse_int(js_lvl.get("buildingLevel"))
                if not name and js_lvl.get("name"):
                    name = _clean_text(js_lvl.get("name"))
                if (js_dur := parse_int(js_lvl.get("duration"))) is not None:
                    duration_s = js_dur
                if (js_gold := parse_int(js_lvl.get("gold"))) is not None:
                    gold = js_gold
                if (js_cp := parse_int(js_lvl.get("capturePoints"))) is not None:
                    cp = js_cp

            levels.append(
                PirateCaptureLevel(
                    requiredLevel=req_level if req_level is not None else (idx * 2 + 1),
                    name=name,
                    durationSeconds=duration_s,
                    goldReward=gold if gold is not None else 0,
                    capturePointsReward=cp if cp is not None else 0,
                    canStart=can_start,
                    actionUrl=action_url,
                    availabilityText=avail_text,
                )
            )

        if not levels and js_levels:
            bld_lvl = parse_int(params.get("buildingLevel")) or self.level or 1
            for js_lvl in js_levels:
                req = parse_int(js_lvl.get("buildingLevel")) or 1
                levels.append(
                    PirateCaptureLevel(
                        requiredLevel=req,
                        name=_clean_text(js_lvl.get("name")),
                        durationSeconds=parse_int(js_lvl.get("duration")),
                        goldReward=parse_int(js_lvl.get("gold")) or 0,
                        capturePointsReward=parse_int(js_lvl.get("capturePoints")) or 0,
                        canStart=(bld_lvl >= req and not params.get("hasOngoingMission")),
                    )
                )

        self.captureLevels = levels

    def _parse_crew_dom(self, soup: BeautifulSoup, params: Dict[str, Any]) -> None:
        """Parse `#tabCrew` capture-point conversion rates and button state."""
        tab = soup.select_one("#tabCrew")
        if tab is not None:
            cp_cost_el = tab.select_one(".costsPerUnit li.capturePoints .value")
            if cp_cost_el is not None:
                cost = parse_int(cp_cost_el.get_text(" ", strip=True))
                if cost is not None:
                    self.crewConversionCost = cost

            per_unit_el = tab.select_one(".costsPerUnit li.time .value")
            if per_unit_el is not None:
                self.crewConversionTimePerUnitSeconds = parse_duration_seconds(
                    per_unit_el.get_text(" ", strip=True)
                )

            hint_el = tab.select_one("#convertHint")
            if hint_el is not None:
                self.crewConversionTimeBaseSeconds = parse_duration_seconds(
                    hint_el.get_text(" ", strip=True)
                )

            crew_form = tab.select_one("#CPToCrewForm")
            has_crew_input = False
            if crew_form is not None:
                self._crew_form_inputs = {
                    str(inp["name"]): str(inp.get("value") or "")
                    for inp in crew_form.find_all("input")
                    if inp.get("name")
                    and str(inp.get("type") or "").lower() not in ("submit", "button", "image", "reset")
                }
                has_crew_input = "crewPoints" in self._crew_form_inputs

        if params:
            if (v := parse_int(params.get("crewConversionFactor"))) is not None:
                self.crewConversionCost = v
            if (v := parse_int(params.get("crewConversionTimeBase"))) is not None:
                self.crewConversionTimeBaseSeconds = v
            if (v := parse_int(params.get("crewConversionTimePerUnit"))) is not None:
                self.crewConversionTimePerUnitSeconds = v

        if tab is not None:
            # `#CPToCrewSubmit` starts with `button_disabled` in SSR HTML until JS validates non-empty input.
            self.canConvertCrew = (
                not self.hasOngoingConversion
                and has_crew_input
                and self.capturePoints >= (self.crewConversionCost or 10)
            )

    def parseBootyQuest(self, viewData: Union[str, AjaxResponse]) -> "PirateFortress":
        """Parse ``activeTab=tabBootyQuest`` response offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabBootyQuest"
        params = _parse_load_js_params(resp)
        self._parse_sidebar(soup, resp)
        self._parse_header_and_highscore(soup, resp, params)
        self._parse_booty_quest_dom(soup, params)
        return self

    def parseCrew(self, viewData: Union[str, AjaxResponse]) -> "PirateFortress":
        """Parse ``activeTab=tabCrew`` response offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabCrew"
        params = _parse_load_js_params(resp)
        self._parse_sidebar(soup, resp)
        self._parse_header_and_highscore(soup, resp, params)
        self._parse_crew_dom(soup, params)
        return self

    async def loadBootyQuest(self) -> "PirateFortress":
        """Fetch and parse ``activeTab=tabBootyQuest``."""
        resp = await self._fetch_view(view="pirateFortress", activeTab="tabBootyQuest")
        return self.parseBootyQuest(resp)

    async def loadCrew(self) -> "PirateFortress":
        """Fetch and parse ``activeTab=tabCrew``."""
        resp = await self._fetch_view(view="pirateFortress", activeTab="tabCrew")
        return self.parseCrew(resp)

    async def loadAllTabs(self) -> "PirateFortress":
        """Refresh the Pirate Fortress view and both tab parsers."""
        await self.load()
        await self.loadCrew()
        return self

    # --- Actions ---

    async def startCaptureRun(self, missionLevel: int = 1) -> AjaxResponse:
        """Start a pirate capture run for ``missionLevel`` (required building level)."""
        from ikabot.ikariam.city import _select_city_id
        from ikabot.ikariam.client import IkariamActionError

        client = self._require_client()
        if not self.isLoaded:
            await self.loadBootyQuest()
        if self.hasOngoingMission:
            raise ValueError("A pirate capture run is already in progress")

        req_level = int(missionLevel)
        level = next(
            (lvl for lvl in self.captureLevels if lvl.requiredLevel == req_level),
            None,
        )
        if level is None:
            available = [lvl.requiredLevel for lvl in self.captureLevels]
            raise ValueError(
                f"Capture mission level {req_level} not found (available: {available})"
            )
        if not level.canStart:
            reason = level.availabilityText or "capture level unavailable"
            raise ValueError(f"Cannot start capture run level {req_level}: {reason}")

        await _select_city_id(
            client,
            self.cityId,
            action_name="PirateFortress.startCaptureRun",
        )
        url = level.actionUrl or (
            f"?action=PiracyScreen&function=capture&buildingLevel={req_level}"
            f"&view=pirateFortress&cityId={self.cityId}&position={self.position or 17}"
        )
        if "activeTab=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}activeTab=tabBootyQuest"

        try:
            resp = await self._post_query_url_action(
                url,
                action_name="PirateFortress.startCaptureRun",
                templateView="pirateFortress",
                metadata={"ambrosia_cost": 0, "missionLevel": req_level},
                refresh=False,
            )
        except IkariamActionError as exc:
            _raise_if_captcha(exc.ajax_response)
            raise

        _raise_if_captcha(resp)
        if resp.view_html:
            self.parseBootyQuest(resp)
        else:
            await self.loadBootyQuest()
        return resp

    async def convertCapturePoints(self, crewPoints: int) -> AjaxResponse:
        """Convert Capture Points into ``crewPoints`` Crew Strength."""
        from ikabot.ikariam.city import _select_city_id

        crew_pts = int(crewPoints)
        if crew_pts <= 0:
            raise ValueError("crewPoints must be a positive integer")

        client = self._require_client()
        if not self.isLoaded or self.activeTab != "tabCrew":
            await self.loadCrew()
        if self.hasOngoingConversion:
            raise ValueError("A capture point conversion is already in progress")
        cost = crew_pts * (self.crewConversionCost or 10)
        if self.capturePoints < cost:
            raise ValueError(
                f"Insufficient capture points ({self.capturePoints}) for {crew_pts} crew (requires {cost})"
            )
        if not self.canConvertCrew:
            raise ValueError("Crew conversion button is currently disabled")

        await _select_city_id(
            client,
            self.cityId,
            action_name="PirateFortress.convertCapturePoints",
        )
        payload = dict(self._crew_form_inputs)
        payload.setdefault("view", "pirateFortress")
        payload["activeTab"] = "tabCrew"
        payload["crewPoints"] = str(crew_pts)
        if "islandId" not in payload and self._last_response and self._last_response.background_data:
            isl_id = self._last_response.background_data.get("islandId")
            if isl_id is not None:
                payload["islandId"] = str(isl_id)

        resp = await self._post_building_action(
            action="PiracyScreen",
            function="convert",
            payloadPost=payload,
            extraParams={"activeTab": "tabCrew"},
            templateView="pirateFortress",
            metadata={"ambrosia_cost": 0, "crewPoints": crew_pts},
            action_name="PirateFortress.convertCapturePoints",
            refresh=False,
        )
        if resp.view_html:
            self.parseCrew(resp)
        else:
            await self.loadCrew()
        return resp

    async def convertGoldToCrew(self, crewPoints: int) -> Any:
        """Convert gold / Ambrosia into Crew Strength (unsupported in `#tabCrew` UI)."""
        ...

    async def raidCity(self, targetCityId: int) -> AjaxResponse:
        """Launch a pirate raid from this fortress against ``targetCityId``."""
        client = self._require_client()
        resp = await execute_piracy_raid(
            client,
            int(targetCityId),
            origin_city_id=self.cityId,
            action_name="PirateFortress.raidCity",
        )
        await self.loadBootyQuest()
        return resp

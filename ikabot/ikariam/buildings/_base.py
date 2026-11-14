"""Shared base class and parsing helpers for Ikariam building models."""

import asyncio
from copy import deepcopy
from datetime import datetime
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import (
    AjaxResponse,
    decode_unicode_escape,
    make_soup,
    parse_ajax_response,
    parse_float,
    parse_int,
    parse_query_params,
)
from ikabot.ikariam.data import Resources

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


_DURATION_UNITS = {
    "w": 7 * 86400,
    "d": 86400,
    "h": 3600,
    "m": 60,
    "s": 1,
}

_RESOURCE_CLASS_TO_KWARG = {
    "wood": "wood",
    "wine": "wine",
    "marble": "marble",
    "crystal": "crystal",
    "glass": "crystal",
    "sulfur": "sulphur",
    "sulphur": "sulphur",
    "gold": "gold",
    "citizens": "citizens",
}


def parse_duration_seconds(text: Optional[str]) -> Optional[int]:
    """Parse an Ikariam duration string such as ``'1D 18h 54m 29s'`` into seconds."""
    if not text:
        return None
    matches = re.findall(r"(\d+)\s*([WwDdHhMmSs])\b", text)
    if not matches:
        return None
    total = 0
    for amount_str, unit in matches:
        total += int(amount_str) * _DURATION_UNITS[unit.lower()]
    return total


def parse_view_payload(
    viewData: Union[str, AjaxResponse],
) -> Tuple[AjaxResponse, BeautifulSoup]:
    """Return ``(AjaxResponse, BeautifulSoup)`` from raw HTML, JSON, or ``AjaxResponse``."""
    if isinstance(viewData, AjaxResponse):
        resp = viewData
    elif isinstance(viewData, str) and viewData.lstrip().startswith("["):
        resp = parse_ajax_response(viewData)
    else:
        resp = AjaxResponse(view_html=viewData if isinstance(viewData, str) else "")
    return resp, make_soup(resp.view_html or "")


def strip_hidden_text(tag: Tag, excluded_classes: Tuple[str, ...] = ("accesshint", "tooltip")) -> str:
    """Return tag text ignoring nested spans/divs with helper CSS classes."""
    clone = deepcopy(tag)
    for cls_name in excluded_classes:
        for child in clone.select(f".{cls_name}"):
            child.decompose()
    return clone.get_text(" ", strip=True)


def _parse_resource_li_amount(li: Tag) -> Optional[int]:
    """Extract an exact integer quantity from a resource ``<li>`` element."""
    title = li.get("title")
    if isinstance(title, str) and title.strip():
        candidate = title.rsplit(":", 1)[-1].strip()
        val = parse_int(candidate)
        if val is not None:
            return val
        for token in reversed(candidate.split()):
            val = parse_int(token)
            if val is not None:
                return val
    return parse_int(strip_hidden_text(li))


def _parse_time_li(li: Tag) -> Tuple[Optional[int], Dict[str, str]]:
    """Extract exact building duration seconds and breakdown table from ``li.time``."""
    breakdown: Dict[str, str] = {}
    seconds: Optional[int] = None

    tooltip = li.find(id="buildingTimeToolTipSidebarContents") or li.select_one(".tooltip")
    if tooltip is not None:
        first_div = tooltip.find("div")
        seconds = parse_duration_seconds(
            first_div.get_text(" ", strip=True) if first_div else tooltip.get_text(" ", strip=True)
        )
        for tr in tooltip.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                label = tds[0].get_text(" ", strip=True)
                value = tds[1].get_text(" ", strip=True)
                if label:
                    breakdown[label] = value

    if seconds is None:
        seconds = parse_duration_seconds(strip_hidden_text(li))
    return seconds, breakdown


def parse_resources_ul(
    ul_tag: Optional[Tag],
) -> Tuple[Resources, List[str], Optional[int], Dict[str, str]]:
    """Parse an Ikariam ``<ul class="resources">`` into ``Resources``, missing keys, duration, and bonuses."""
    kwargs: Dict[str, int] = {}
    missing: List[str] = []
    duration_seconds: Optional[int] = None
    time_breakdown: Dict[str, str] = {}

    if ul_tag is None:
        return Resources(), missing, duration_seconds, time_breakdown

    for li in ul_tag.find_all("li", recursive=False):
        classes = list(li.get("class") or [])
        if "time" in classes:
            duration_seconds, time_breakdown = _parse_time_li(li)
            continue

        res_key: Optional[str] = None
        for cls in classes:
            if cls in _RESOURCE_CLASS_TO_KWARG:
                res_key = _RESOURCE_CLASS_TO_KWARG[cls]
                break
        if res_key is None:
            continue

        amount = _parse_resource_li_amount(li)
        if amount is not None:
            kwargs[res_key] = amount
        if "red" in classes and res_key not in missing:
            missing.append(res_key)

    return Resources(**kwargs), missing, duration_seconds, time_breakdown


def tmpl_value(resp: AjaxResponse, key: str, field: str = "text") -> Any:
    """Safely extract a field or raw value from ``AjaxResponse.template_data``."""
    entry = resp.template_data.get(key)
    if isinstance(entry, dict):
        return entry.get(field)
    return entry if field == "text" else None


def tmpl_text(resp: AjaxResponse, key: str) -> str:
    """Return stripped text from ``template_data[key]`` whether dict or scalar."""
    val = tmpl_value(resp, key, "text")
    return "" if val is None else str(val).strip()


def tmpl_int(resp: AjaxResponse, key: str, field: str = "text") -> Optional[int]:
    """Parse an integer from ``template_data[key]`` (preferring ``tooltip`` if requested)."""
    return parse_int(tmpl_value(resp, key, field))


def extract_building_countdown(soup: BeautifulSoup) -> Dict[str, Optional[float]]:
    """Extract JS ``ikariam.getScreen().buildingCountdown`` properties if present."""
    result: Dict[str, Optional[float]] = {
        "progress": None,
        "startdate": None,
        "duration": None,
    }
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if "buildingCountdown" not in text:
            continue
        for key in ("progress", "startdate", "duration"):
            match = re.search(rf"buildingCountdown\.{key}\s*=\s*([0-9.+-]+)", text)
            if match:
                result[key] = parse_float(match.group(1))
    return result


def parse_labeled_coords(text: str) -> Tuple[str, int, int]:
    """Parse an Ikariam island coordinate string such as ``'Syfios [32:33]'`` or ``'[32:33] Lispo'``."""
    match = re.search(r"\[(\d+):(\d+)\]", text)
    if not match:
        return text.strip(), 0, 0
    x = int(match.group(1))
    y = int(match.group(2))
    name = (text[: match.start()] + text[match.end() :]).strip()
    return name, x, y


class Building:
    """Base model representing an existing building plot in an Ikariam city."""

    client: Optional["Client"]
    city: Optional["City"]
    cityId: int
    position: Optional[int]
    buildingId: Optional[int] = None
    buildingType: str = ""
    name: str
    level: int
    canUpgrade: bool
    isMaxLevel: bool
    isBusy: bool
    groundId: int
    allowedBuildings: List[int]
    isUnderConstruction: bool
    completedTime: Optional[datetime]
    countdownText: Optional[str]

    isLoaded: bool
    upgradeCost: Optional[Resources]
    missingUpgradeResources: List[str]
    upgradeTimeSeconds: Optional[int]
    upgradeTimeBreakdown: Dict[str, str]
    nextUpgradeLevel: Optional[int]
    canDemolish: bool
    upgradeUrl: Optional[str]
    demolishUrl: Optional[str]
    cancelUpgradeUrl: Optional[str]
    constructionTargetLevel: Optional[int]
    constructionProgress: Optional[float]
    constructionStartTime: Optional[datetime]
    constructionDurationSeconds: Optional[int]
    speedupAvailable: bool
    speedupFree: bool
    speedupUrl: Optional[str]

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: Optional[int] = 0,
        position: Optional[int] = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize building identity from city plot data without making HTTP calls."""
        self.client = client
        self.city = city
        self.cityId = cityId if cityId else (city.id if city is not None else 0)
        self.position = position

        self.buildingId = getattr(type(self), "buildingId", None)
        self.buildingType = getattr(type(self), "buildingType", "")
        self.name = ""
        self.level = 0
        self.canUpgrade = False
        self.isMaxLevel = False
        self.isBusy = False
        self.groundId = 0
        self.allowedBuildings = []
        self.isUnderConstruction = False
        self.completedTime = None
        self.countdownText = None

        self.isLoaded = False
        self.upgradeCost = None
        self.missingUpgradeResources = []
        self.upgradeTimeSeconds = None
        self.upgradeTimeBreakdown = {}
        self.nextUpgradeLevel = None
        self.canDemolish = False
        self.upgradeUrl = None
        self.demolishUrl = None
        self.cancelUpgradeUrl = None
        self.constructionTargetLevel = None
        self.constructionProgress = None
        self.constructionStartTime = None
        self.constructionDurationSeconds = None
        self.speedupAvailable = False
        self.speedupFree = False
        self.speedupUrl = None

        self._raw_position_data = data or {}
        self._last_response: Optional[AjaxResponse] = None
        if data:
            self._init_from_position_data(data)

    def _init_from_position_data(self, data: Dict[str, Any]) -> None:
        """Populate plot summary fields from an ``updateBackgroundData.position`` entry."""
        self._raw_position_data = data
        raw_building = str(data.get("building") or "").strip()
        if raw_building:
            self.buildingType = raw_building.split()[0]
            self.isUnderConstruction = "constructionSite" in raw_building
        else:
            self.isUnderConstruction = False

        self.buildingId = parse_int(data.get("buildingId"))
        if data.get("name") is not None:
            self.name = decode_unicode_escape(str(data.get("name")))
        self.level = parse_int(data.get("level")) or 0
        self.canUpgrade = bool(data.get("canUpgrade", False))
        self.isMaxLevel = bool(data.get("isMaxLevel", False))
        self.isBusy = bool(data.get("isBusy", False))
        self.groundId = parse_int(data.get("groundId")) or 0
        allowed = data.get("allowedBuildings")
        self.allowedBuildings = (
            [int(bid) for bid in allowed if parse_int(bid) is not None]
            if isinstance(allowed, list)
            else []
        )
        completed_ts = parse_int(data.get("completed"))
        self.completedTime = (
            datetime.fromtimestamp(completed_ts) if completed_ts and completed_ts > 0 else None
        )
        countdown_raw = data.get("countdownText")
        self.countdownText = str(countdown_raw) if countdown_raw else None

    def _require_client(self) -> "Client":
        """Return the attached :class:`Client` or raise if building is detached."""
        if self.client is None:
            raise RuntimeError("Cannot perform building operation without an attached Client")
        return self.client

    async def _fetch_view(
        self,
        view: Optional[str] = None,
        activeTab: Optional[str] = None,
        extraParams: Optional[Dict[str, str]] = None,
    ) -> AjaxResponse:
        """Fetch an AJAX view payload scoped to this building's city and position."""
        client = self._require_client()
        view_name = view or self.buildingType
        if not view_name:
            raise ValueError("Building view name is unknown")
        params: Dict[str, str] = {
            "view": view_name,
            "cityId": str(self.cityId),
            "backgroundView": "city",
            "currentCityId": str(self.cityId),
            "templateView": view_name,
            "actionRequest": "REQUESTID",
        }
        if self.position is not None:
            params["position"] = str(self.position)
        if activeTab is not None:
            params["activeTab"] = activeTab
        if extraParams:
            params.update(extraParams)
        return await client.post_ajax(params=params)

    async def _post_building_action(
        self,
        *,
        action: str,
        function: str,
        payloadPost: Optional[Dict[str, Any]] = None,
        extraParams: Optional[Dict[str, Any]] = None,
        templateView: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        action_name: str = "",
        refresh: bool = True,
    ) -> AjaxResponse:
        """Execute a building-scoped POST action via ``client.post_action`` and refresh state."""
        client = self._require_client()
        view_name = templateView or self.buildingType or ""
        params: Dict[str, Any] = {
            "backgroundView": "city",
            "currentCityId": str(self.cityId),
            "actionRequest": "REQUESTID",
        }
        if view_name:
            params["templateView"] = view_name
        if extraParams:
            params.update(extraParams)

        payload: Dict[str, Any] = {
            "action": action,
            "function": function,
            "cityId": str(self.cityId),
        }
        if self.position is not None:
            payload["position"] = str(self.position)
        if payloadPost:
            payload.update(payloadPost)

        resp = await client.post_action(
            payloadPost=payload,
            params=params,
            metadata=metadata,
            action_name=action_name,
        )
        if refresh:
            if resp.view_html:
                self.parseView(resp)
            elif self.buildingType:
                await self.load()
        return resp

    async def _post_query_url_action(
        self,
        url: str,
        *,
        action_name: str,
        templateView: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        refresh: bool = True,
    ) -> AjaxResponse:
        """Send an Ikariam query-string action URL via ``client.post_action`` and refresh."""
        client = self._require_client()
        params = parse_query_params(url)
        params.setdefault("backgroundView", "city")
        params.setdefault("currentCityId", str(self.cityId))
        view_name = templateView or self.buildingType or ""
        if view_name:
            params.setdefault("templateView", view_name)
        params["actionRequest"] = "REQUESTID"

        resp = await client.post_action(
            params=params,
            metadata=metadata,
            action_name=action_name,
        )
        if refresh:
            if resp.view_html:
                self.parseView(resp)
            elif self.buildingType:
                await self.load()
        return resp

    async def _fetch_popup_soup(self, url: str, *, window_name: Optional[str] = None) -> BeautifulSoup:
        """Fetch an Ikariam popup window URL and parse its HTML body."""
        client = self._require_client()
        params = parse_query_params(url)
        params.setdefault("backgroundView", "city")
        params.setdefault("currentCityId", str(self.cityId))
        params["actionRequest"] = "REQUESTID"
        resp = await client.post_ajax(params=params)
        html_body = resp.get_window_html(window_name) or resp.get_window_html() or resp.view_html or ""
        return make_soup(html_body)

    async def load(self) -> "Building":
        """Load the building's primary view from Ikariam and populate parsed fields."""
        resp = await self._fetch_view()
        return self.parseView(resp)

    def parseView(self, viewData: Union[str, AjaxResponse]) -> "Building":
        """Parse a building view response (HTML, raw JSON, or :class:`AjaxResponse`)."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp

        if resp.background_data:
            bg_city_id = parse_int(resp.background_data.get("id"))
            if bg_city_id and not self.cityId:
                self.cityId = bg_city_id
            positions = resp.background_data.get("position")
            if isinstance(positions, list) and self.position is not None and 0 <= self.position < len(positions):
                entry = positions[self.position]
                if isinstance(entry, dict) and entry.get("building") not in (None, "empty"):
                    self._init_from_position_data(entry)

        self._parse_upgrade_sidebar(soup, resp)
        self._parse_body(soup, resp)
        self.isLoaded = True
        return self

    def _parse_upgrade_sidebar(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse ``#buildingUpgrade`` costs, timing, demolish availability, and queue status."""
        self.upgradeCost = None
        self.missingUpgradeResources = []
        self.upgradeTimeSeconds = None
        self.upgradeTimeBreakdown = {}
        self.nextUpgradeLevel = None
        self.canDemolish = False
        self.upgradeUrl = None
        self.demolishUrl = None
        self.cancelUpgradeUrl = None
        self.constructionTargetLevel = None
        self.constructionProgress = None
        self.constructionStartTime = None
        self.constructionDurationSeconds = None
        self.speedupAvailable = False
        self.speedupFree = False
        self.speedupUrl = None

        upg = soup.find(id="buildingUpgrade")
        if upg is not None:
            show_lvl = upg.select_one("li.showLevel")
            if show_lvl is not None:
                lvl_text = strip_hidden_text(show_lvl, ("textLabel",))
                parsed_lvl = parse_int(lvl_text)
                if parsed_lvl is not None:
                    self.level = parsed_lvl

            upg_btn = upg.select_one("#js_buildingUpgradeButton, li.upgrade a")
            if upg_btn is not None and upg_btn.get("href"):
                self.upgradeUrl = str(upg_btn["href"])

            dem_btn = upg.select_one("li.downgrade a")
            if dem_btn is not None:
                self.canDemolish = True
                if dem_btn.get("href"):
                    self.demolishUrl = str(dem_btn["href"])

            h4 = upg.find("h4")
            if h4 is not None:
                match = re.search(r"(\d+)", h4.get_text(" ", strip=True))
                if match:
                    self.nextUpgradeLevel = int(match.group(1))

            res_ul = upg.select_one("ul.resources")
            if res_ul is not None:
                cost, missing, secs, breakdown = parse_resources_ul(res_ul)
                self.upgradeCost = cost
                self.missingUpgradeResources = missing
                self.upgradeTimeSeconds = secs
                self.upgradeTimeBreakdown = breakdown

        uip = soup.find(id="upgradeInProgress")
        if uip is not None:
            self.isUnderConstruction = True
            spans = uip.select(".buildingLevel span.bold")
            if len(spans) >= 2:
                self.constructionTargetLevel = parse_int(spans[-1].get_text(strip=True))
            bar = uip.find(id="upgradeProgress")
            if bar is not None:
                self.constructionProgress = parse_float(bar.get("title"))
            spd = uip.find(id="buildingSpeedupBuilding")
            if spd is not None:
                self.speedupAvailable = True
                onclick = str(spd.get("onclick") or "")
                m_spd = re.search(r"ajaxHandlerCall\('([^']+)'\)", onclick)
                if m_spd:
                    self.speedupUrl = m_spd.group(1)

        cancel_btn = soup.select_one(
            "#demolition a[href*='CancelBuildingUpgrade'], "
            "#upgradeInProgress a[href*='CancelBuildingUpgrade']"
        )
        if cancel_btn is not None and cancel_btn.get("href"):
            self.cancelUpgradeUrl = str(cancel_btn["href"])

        countdown = extract_building_countdown(soup)
        if countdown["progress"] is not None:
            self.constructionProgress = countdown["progress"]
        if countdown["startdate"] is not None:
            self.constructionStartTime = datetime.fromtimestamp(countdown["startdate"] / 1000.0)
        if countdown["duration"] is not None:
            self.constructionDurationSeconds = int(round(countdown["duration"] / 1000.0))
            if countdown["startdate"] is not None and self.completedTime is None:
                self.completedTime = datetime.fromtimestamp(
                    (countdown["startdate"] + countdown["duration"]) / 1000.0
                )

        speedup_tmpl = resp.template_data.get("buildingSpeedupBuilding") or resp.template_data.get(
            "buildingSpeedupConstructionList"
        )
        if isinstance(speedup_tmpl, dict):
            timeout = speedup_tmpl.get("timeout")
            if isinstance(timeout, dict):
                self.speedupFree = timeout.get("className") == "free"

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Hook for building-specific subclasses to extract view data."""

    async def upgrade(self) -> "Building":
        """Upgrade this building by one level."""
        if not self.upgradeUrl:
            await self.load()
        if not self.upgradeUrl:
            raise ValueError(
                f"Building {self.buildingType}@{self.cityId}:{self.position} cannot be upgraded"
            )
        await self._post_query_url_action(
            self.upgradeUrl,
            action_name="Building.upgrade",
            metadata={"ambrosia_cost": 0},
            refresh=True,
        )
        return self

    async def demolish(self) -> "Building":
        """Downgrade or demolish this building after confirming the demolition popup."""
        if not self.demolishUrl:
            await self.load()
        if not self.canDemolish or not self.demolishUrl:
            raise ValueError(
                f"Building {self.buildingType}@{self.cityId}:{self.position} cannot be demolished"
            )

        popup_soup = await self._fetch_popup_soup(
            self.demolishUrl,
            window_name="buildings_demolition",
        )
        yes_btn = popup_soup.select_one(
            "#js_demolitionYesBtn, a[href*='demolishBuilding']"
        )
        confirm_href = str(yes_btn["href"]) if yes_btn and yes_btn.get("href") else None
        if not confirm_href:
            raise ValueError("Missing demolition confirmation link in buildings_demolition popup")

        prev_level = self.level
        resp = await self._post_query_url_action(
            confirm_href,
            action_name="Building.demolish",
            metadata={"ambrosia_cost": 0},
            refresh=False,
        )
        if prev_level <= 1:
            self.level = 0
            self.isUnderConstruction = False
            self.canUpgrade = False
            self.canDemolish = False
            self.upgradeUrl = None
            self.demolishUrl = None
            self.cancelUpgradeUrl = None
            self.speedupUrl = None
        elif resp.view_html and (
            "buildingUpgrade" in resp.view_html or "upgradeInProgress" in resp.view_html
        ):
            self.parseView(resp)
        elif self.buildingType:
            await self.load()
        return self

    async def cancelUpgrade(self) -> "Building":
        """Cancel the upgrade currently in progress on this building."""
        if not self.cancelUpgradeUrl:
            await self.load()
        if not self.cancelUpgradeUrl:
            raise ValueError(
                f"Building {self.buildingType}@{self.cityId}:{self.position} has no active upgrade to cancel"
            )

        prev_level = self.level
        resp = await self._post_query_url_action(
            self.cancelUpgradeUrl,
            action_name="Building.cancelUpgrade",
            metadata={"ambrosia_cost": 0},
            refresh=False,
        )
        if prev_level <= 0:
            self.level = 0
            self.isUnderConstruction = False
            self.cancelUpgradeUrl = None
            self.speedupAvailable = False
            self.speedupUrl = None
            self.constructionTargetLevel = None
            self.completedTime = None
        elif resp.view_html and (
            "buildingUpgrade" in resp.view_html or "upgradeInProgress" in resp.view_html
        ):
            self.parseView(resp)
        elif self.buildingType:
            await self.load()
        return self

    async def speedup(self) -> "Building":
        """Complete an active upgrade using verified 0-Ambrosia speedup step(s).

        Ikariam's free ``< 5 min`` speedup can require a first ``halve`` action
        followed by an ``instantly complete`` action (both costing 0 Ambrosia).
        """
        if not self.speedupUrl:
            await self.load()
        if not self.speedupUrl:
            raise ValueError(
                f"Building {self.buildingType}@{self.cityId}:{self.position} has no speedup option"
            )

        for step in range(5):
            if not self.speedupUrl:
                break
            popup_soup = await self._fetch_popup_soup(
                self.speedupUrl,
                window_name="buildingSpeedup",
            )
            act_btn = popup_soup.select_one(
                "#js_buildingSpeedupActivateBtn, a[href*='buildingSpeedup']"
            )
            if act_btn is None or not act_btn.get("href"):
                if step == 0:
                    raise ValueError("Missing speedup activation link in buildingSpeedup popup")
                break

            amb_span = act_btn.select_one("span.ambrosiaIcon")
            cost = parse_int(amb_span.get_text(strip=True)) if amb_span is not None else None
            if cost is None or cost != 0:
                if step == 0:
                    from ikabot.ikariam.client import AmbrosiaBlockedError

                    raise AmbrosiaBlockedError(
                        f"Building.speedup refused: speedup cost is {cost!r} Ambrosia (must be 0)"
                    )
                break

            prev_level = self.level
            await self._post_query_url_action(
                str(act_btn["href"]),
                action_name="Building.speedup",
                metadata={"ambrosia_cost": 0},
                refresh=False,
            )
            if self.buildingType:
                await asyncio.sleep(0.3)
                await self.load()
            if not self.isUnderConstruction or self.level > prev_level:
                break
        return self

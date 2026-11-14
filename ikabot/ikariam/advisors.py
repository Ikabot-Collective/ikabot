"""Ikariam advisor views, sub-tabs, and action stubs (Mayor, Military, Research, Diplomacy)."""

from datetime import datetime
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import (
    AjaxResponse,
    Table,
    decode_unicode_escape,
    make_soup,
    parse_float,
    parse_int,
    parse_query_int,
    parse_query_params,
    parse_query_str,
)
from ikabot.ikariam.buildings._base import (
    parse_duration_seconds,
    parse_view_payload,
    tmpl_text,
)
from ikabot.ikariam.city import _parse_countdown_entry, _parse_pure_int
from ikabot.ikariam.data import (
    MayorMessage,
    MilitaryMovement,
    MovementNode,
    Resources,
    Units,
)

if TYPE_CHECKING:
    from ikabot.ikariam.client import Client


_TAB_COUNT_RE = re.compile(r"\((\d[\d,.\s]*)\)\s*$")
_COORDS_RE = re.compile(r"\[(\d+):(\d+)\]")
_PAIR_COUNT_RE = re.compile(r"\((\d+)\s*/\s*(\d+)\)")
_DATE_FORMATS = ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y")


def _parse_date(text: str) -> Optional[datetime]:
    """Parse an Ikariam date/timestamp string into a ``datetime``, or ``None``."""
    cleaned = text.strip()
    if not cleaned:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _extract_flag_tag(cell_tag: Optional[Tag]) -> str:
    """Extract the country/visibility flag class from a ``span.flag`` element."""
    if cell_tag is None:
        return ""
    flag_span = cell_tag.find("span", class_="flag")
    if flag_span is None:
        return ""
    return next((cls for cls in (flag_span.get("class") or []) if cls != "flag"), "")


def _parse_movement_node(node: dict) -> MovementNode:
    """Build a :class:`MovementNode` from an Ikariam military movement origin or target dict."""
    return MovementNode(
        cityName=decode_unicode_escape(node.get("name") or ""),
        playerId=parse_int(node.get("avatarId")),
        playerName=decode_unicode_escape(node.get("avatarName") or ""),
        cityId=parse_int(node.get("cityId")),
        islandId=parse_int(node.get("islandId")),
    )


def _extract_coords(text: str) -> Tuple[Optional[str], Optional[Tuple[int, int]]]:
    """Split ``'Town [x:y]'`` or ``'[x:y] Town'`` into ``(name, (x, y))``."""
    stripped = text.strip()
    if not stripped:
        return None, None
    match = _COORDS_RE.search(stripped)
    if not match:
        return stripped, None
    coords = (int(match.group(1)), int(match.group(2)))
    name = (stripped[: match.start()] + stripped[match.end() :]).strip() or None
    return name, coords


def _parse_tab_counts(soup: BeautifulSoup) -> Dict[str, int]:
    """Extract ``(N)`` counts keyed by tab DOM ``id`` across ``ul.tabmenu`` items."""
    counts: Dict[str, int] = {}
    for li in soup.select("ul.tabmenu li"):
        tab_id = li.get("id")
        if not tab_id:
            continue
        match = _TAB_COUNT_RE.search(li.get_text(" ", strip=True))
        if match:
            val = parse_int(match.group(1))
            if val is not None:
                counts[str(tab_id)] = val
    return counts


def _parse_select_selected(
    form: Tag,
    field_name: str,
) -> Tuple[Optional[int], Optional[str], List[Tuple[int, str]]]:
    """Return ``(selected_id, selected_label, all_options)`` for a ``<select>`` element."""
    select = form.find("select", attrs={"name": field_name})
    if select is None:
        return None, None, []
    selected_id: Optional[int] = None
    selected_label: Optional[str] = None
    options: List[Tuple[int, str]] = []
    for opt in select.find_all("option"):
        val_raw = opt.get("value")
        val_int = _parse_pure_int(str(val_raw)) if val_raw is not None else None
        label = opt.get_text(" ", strip=True).replace("\xa0", " ").strip()
        if val_int is not None:
            options.append((val_int, label))
            if opt.has_attr("selected"):
                selected_id = val_int
                selected_label = label
    return selected_id, selected_label, options


def _parse_pair_header_count(
    soup: BeautifulSoup,
    prefix: str,
) -> Tuple[Optional[int], Optional[int]]:
    """Extract ``(count, max_count)`` from a heading beginning with ``prefix``."""
    for h3 in soup.select("h3.header"):
        text = h3.get_text(" ", strip=True)
        if text.lower().startswith(prefix.lower()):
            match = _PAIR_COUNT_RE.search(text)
            if match:
                return int(match.group(1)), int(match.group(2))
    return None, None


def _extract_paginator_links(
    soup: BeautifulSoup,
    current_offset: int,
) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, str]]]:
    """Return ``(prev_params, next_params)`` from ``a.paginator_link`` anchors."""
    prev_candidates: List[Tuple[int, Dict[str, str]]] = []
    next_candidates: List[Tuple[int, Dict[str, str]]] = []
    for link in soup.select("a.paginator_link"):
        href = link.get("href")
        if not href:
            continue
        href_str = str(href)
        query = href_str.split("?", 1)[1] if "?" in href_str else href_str.lstrip("/")
        params = {k: v[-1] for k, v in parse_qs(query).items() if v}
        link_offset = parse_int(params.get("offset"))
        if link_offset is None:
            link_offset = parse_int(params.get("start"))
        if link_offset is None:
            continue
        if link_offset < current_offset:
            prev_candidates.append((link_offset, params))
        elif link_offset > current_offset:
            next_candidates.append((link_offset, params))
    prev_params = max(prev_candidates, key=lambda item: item[0])[1] if prev_candidates else None
    next_params = min(next_candidates, key=lambda item: item[0])[1] if next_candidates else None
    return prev_params, next_params


# ---------------------------------------------------------------------------
# Mayor / Trade Advisor
# ---------------------------------------------------------------------------


class MayorMessageTable(Table):
    """Parsed mayor / trade advisor inbox message table."""

    view: "MayorView"
    rows: List[MayorMessage]

    def __init__(self, view: "MayorView", tableHTML: Union[str, Tag]) -> None:
        """Parse mayor event rows from ``table#inboxCity`` HTML or tag."""
        self.view = view
        super().__init__(tableHTML)
        self.rows = []
        for row in self._rows:
            if "pgnt" in row.classes or len(row._cells) < 4:
                continue
            cells = row._cells
            cat_span = cells[0].tag.find("span", class_="category")
            if cat_span is None:
                continue

            msg_type = next(
                (cls for cls in (cat_span.get("class") or []) if cls != "category"),
                "",
            )
            is_new = "highlight" in row.classes
            city_name = cells[1].text
            city_a = cells[1].tag.find("a")
            city_id = (
                (parse_query_int(city_a.get("href"), "cityId") or 0)
                if city_a is not None
                else 0
            )

            parsed_date = _parse_date(cells[2].text) or datetime.min
            subject_html = cells[3]._content.strip()
            subject_text = make_soup(subject_html).get_text(" ", strip=True)
            self.rows.append(
                MayorMessage(
                    msg_type,
                    is_new,
                    city_name,
                    city_id,
                    parsed_date,
                    subject_html,
                    subject=subject_text,
                )
            )


class MayorView:
    """Mayor / trade advisor view with message table, filter state, and pagination."""

    client: "Client"
    mayorMessageTable: MayorMessageTable
    currentMessageRange: Tuple[int, int]
    totalMessages: int
    toggledFilters: List[str]

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse mayor messages, total count, range, filters, and paginator links."""
        self.client = client
        self.__mayor_view_view_data = viewData

        resp, soup = parse_view_payload(viewData)
        self._mayor_response = resp
        table_tag = soup.find("table", id="inboxCity") or soup.find("table")
        self.mayorMessageTable = MayorMessageTable(
            self,
            table_tag if table_tag is not None else "",
        )

        self.totalMessages = 0
        for heading in soup.find_all("h3", class_="header"):
            match = re.search(r"\((\d[\d,.\s\xa0]*)\)", heading.get_text())
            if match:
                parsed_total = parse_int(match.group(1))
                if parsed_total is not None:
                    self.totalMessages = parsed_total
                    break

        range_div = soup.select_one("div.paginator_link.bold")
        if range_div is not None:
            range_match = re.search(r"(\d+)\s*-\s*(\d+)", range_div.get_text(strip=True))
            if range_match:
                self.currentMessageRange = (
                    int(range_match.group(1)),
                    int(range_match.group(2)),
                )
            else:
                self.currentMessageRange = (0, 0)
        else:
            self.currentMessageRange = (0, 0)

        filter_container = soup.find("form", id="filterForm") or soup
        self.toggledFilters = [
            str(cb["name"])
            for cb in filter_container.select('input[type="checkbox"]')
            if cb.has_attr("checked") and cb.get("name")
        ]

        current_offset = max(0, self.currentMessageRange[0] - 1)
        self._prevLinkParams, self._nextLinkParams = _extract_paginator_links(
            soup, current_offset
        )

    async def getPreviousPage(self) -> "MayorView":
        """Fetch the previous page of mayor events."""
        if self._prevLinkParams is not None:
            resp = await self.client.get_ajax(params=self._prevLinkParams)
            if resp.view_html is None:
                raise ValueError("Missing view HTML in mayor advisor response")
            return MayorView(self.client, resp)
        prev_offset = (
            max(0, (self.currentMessageRange[0] - 1) - 10)
            if self.currentMessageRange[0] > 1
            else 0
        )
        return await self.client.getMayorView(offset=prev_offset)

    async def getNextPage(self) -> "MayorView":
        """Fetch the next page of mayor events."""
        if self._nextLinkParams is not None:
            resp = await self.client.get_ajax(params=self._nextLinkParams)
            if resp.view_html is None:
                raise ValueError("Missing view HTML in mayor advisor response")
            return MayorView(self.client, resp)
        next_offset = self.currentMessageRange[1] if self.currentMessageRange[1] > 0 else 0
        return await self.client.getMayorView(offset=next_offset)

    async def toggleFilter(self, mayorMessageType: str) -> "MayorView":
        """Toggle a message category filter from :class:`MayorMessageTypes` and reload."""
        new_filters = list(self.toggledFilters)
        if mayorMessageType in new_filters:
            new_filters.remove(mayorMessageType)
        else:
            new_filters.append(mayorMessageType)

        payload: Dict[str, str] = {
            "view": "tradeAdvisor",
            "filter": "1",
        }
        for msg_type in new_filters:
            payload[msg_type] = "on"

        resp = await self.client.post_ajax(payloadPost=payload)
        if resp.view_html is None:
            raise ValueError("Missing view HTML in mayor advisor response")
        return MayorView(self.client, resp)

    async def getTradeRoutes(self, page: int = 0) -> "TradeRoutesView":
        """Switch to the Mayor Trade Routes tab (read-only)."""
        return await self.client.getTradeRoutesView(page=page)


class TradeRouteEntry:
    """Single configured or editable trade route slot in the Trade Routes tab."""

    position: int
    sourceCityId: Optional[int]
    sourceCityName: Optional[str]
    destinationCityId: Optional[int]
    destinationCityName: Optional[str]
    resourceTypeId: Optional[int]
    resourceName: Optional[str]
    amount: int
    hour: Optional[int]
    durationText: Optional[str]
    isActive: bool
    renewFlag: int
    deleteHref: Optional[str]
    cityOptions: List[Tuple[int, str]]
    updatePosition: int

    def __init__(
        self,
        *,
        position: int,
        sourceCityId: Optional[int],
        sourceCityName: Optional[str],
        destinationCityId: Optional[int],
        destinationCityName: Optional[str],
        resourceTypeId: Optional[int],
        resourceName: Optional[str],
        amount: int,
        hour: Optional[int],
        durationText: Optional[str],
        isActive: bool,
        renewFlag: int,
        deleteHref: Optional[str],
        cityOptions: List[Tuple[int, str]],
        updatePosition: int = 0,
    ) -> None:
        self.position = position
        self.sourceCityId = sourceCityId
        self.sourceCityName = sourceCityName
        self.destinationCityId = destinationCityId
        self.destinationCityName = destinationCityName
        self.resourceTypeId = resourceTypeId
        self.resourceName = resourceName
        self.amount = amount
        self.hour = hour
        self.durationText = durationText
        self.isActive = isActive
        self.renewFlag = renewFlag
        self.deleteHref = deleteHref
        self.cityOptions = cityOptions
        self.updatePosition = updatePosition if updatePosition else (position + 1)


class TradeRoutesView:
    """Mayor Trade Routes tab view (``view=tradeRoutes``)."""

    client: "Client"
    page: int
    routes: List[TradeRouteEntry]
    newTradeRouteHref: Optional[str]

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse trade route forms and slot metadata."""
        self.client = client
        self._parse_trade_routes(viewData)

    def _parse_trade_routes(self, viewData: Union[str, AjaxResponse]) -> None:
        """Populate ``page``, ``routes``, and ``newTradeRouteHref`` from view data."""
        resp, soup = parse_view_payload(viewData)
        self._trade_routes_response = resp
        self.routes = []
        self.page = 0

        for idx, form in enumerate(soup.select("form[id^='tradeRouteForm']")):
            pos_input = form.find("input", attrs={"name": "position"})
            upd_input = form.find("input", attrs={"name": "updatePosition"})
            page_input = form.find("input", attrs={"name": "page"})
            if idx == 0 and page_input and page_input.get("value") is not None:
                self.page = parse_int(str(page_input["value"])) or 0
            position = (
                parse_int(str(pos_input["value"]))
                if pos_input and pos_input.get("value") is not None
                else idx
            )
            eff_pos = position if position is not None else idx
            upd_pos = (
                parse_int(str(upd_input["value"]))
                if upd_input and upd_input.get("value") is not None
                else None
            ) or (eff_pos + 1)
            src_id, src_name, city_opts = _parse_select_selected(form, "city1Id")
            dst_id, dst_name, dst_opts = _parse_select_selected(form, "city2Id")
            if not city_opts:
                city_opts = dst_opts
            res_id, res_name, _ = _parse_select_selected(form, "tradegood")
            hour, _, _ = _parse_select_selected(form, "time")

            num_input = form.find("input", attrs={"name": "number"})
            amount = (
                parse_int(str(num_input["value"]))
                if num_input and num_input.get("value") is not None
                else 0
            ) or 0

            renew_input = form.find("input", attrs={"name": "renew"})
            renew_flag = (
                parse_int(str(renew_input["value"]))
                if renew_input and renew_input.get("value") is not None
                else 0
            ) or 0

            title_div = form.find_previous_sibling("div", class_="title_row")
            duration_text = (
                " ".join(title_div.get_text(" ", strip=True).replace("\xa0", " ").split())
                if title_div is not None
                else None
            )

            delete_link = form.select_one("a[href*='deleteTradeRoute']")
            activate_link = form.select_one("a[onclick*='renew']")
            is_active = activate_link is None and src_id is not None and dst_id is not None

            self.routes.append(
                TradeRouteEntry(
                    position=eff_pos,
                    sourceCityId=src_id,
                    sourceCityName=src_name,
                    destinationCityId=dst_id,
                    destinationCityName=dst_name,
                    resourceTypeId=res_id,
                    resourceName=res_name,
                    amount=amount,
                    hour=hour,
                    durationText=duration_text,
                    isActive=is_active,
                    renewFlag=renew_flag,
                    deleteHref=(
                        str(delete_link["href"])
                        if delete_link and delete_link.get("href")
                        else None
                    ),
                    cityOptions=city_opts,
                    updatePosition=upd_pos,
                )
            )

        new_link = soup.select_one("a[href*='newTradeRoute=1']")
        self.newTradeRouteHref = (
            str(new_link["href"]) if new_link and new_link.get("href") else None
        )

    async def getTownNews(self, offset: int = 0) -> MayorView:
        """Switch back to the Mayor Town News tab (read-only)."""
        return await self.client.getMayorView(offset=offset)

    async def saveTradeRoute(
        self,
        position: int,
        *,
        sourceCityId: int,
        destinationCityId: int,
        resourceTypeId: int,
        amount: int,
        hour: int,
    ) -> AjaxResponse:
        """Save edited parameters for the trade route at ``position`` without spending Ambrosia."""
        if amount < 0:
            raise ValueError(f"Trade route amount cannot be negative ({amount})")
        if not 0 <= int(hour) <= 23:
            raise ValueError(f"Trade route hour must be between 0 and 23 (got {hour})")
        route = next((r for r in self.routes if r.position == position), None)
        update_pos = (
            route.updatePosition
            if route is not None and route.updatePosition
            else (int(position) + 1)
        )
        payload: Dict[str, str] = {
            "action": "Premium",
            "function": "editTradeRoute",
            "updatePosition": str(update_pos),
            "renew": "0",
            "oldView": "tradeRoutes",
            "activeTab": "tabTradeRoutes",
            "page": str(self.page),
            "cityId": "0",
            "position": str(position),
            "city1Id": str(sourceCityId),
            "city2Id": str(destinationCityId),
            "number": str(amount),
            "tradegood": str(resourceTypeId),
            "time": str(hour),
        }
        params: Dict[str, str] = {
            "backgroundView": "city",
            "templateView": "tradeRoutes",
            "actionRequest": "REQUESTID",
        }
        if self.client.selectedDropDownCity is not None:
            params["currentCityId"] = str(self.client.selectedDropDownCity.id)

        resp = await self.client.post_action(
            payloadPost=payload,
            params=params,
            metadata={"ambrosia_cost": 0},
            action_name="TradeRoutesView.saveTradeRoute",
        )
        if resp.view_html and "tradeRouteForm" in resp.view_html:
            self._parse_trade_routes(resp)
        else:
            refreshed = await self.client.getTradeRoutesView(page=self.page)
            self._trade_routes_response = refreshed._trade_routes_response
            self.page = refreshed.page
            self.routes = refreshed.routes
            self.newTradeRouteHref = refreshed.newTradeRouteHref
        return resp

    async def activateTradeRoute(self, position: int) -> AjaxResponse:
        """Activate or renew the trade route slot at ``position``."""
        ...

    async def deleteTradeRoute(self, position: int) -> AjaxResponse:
        """Delete the trade route configured at ``position``."""
        ...

    async def createTradeRoute(
        self,
        *,
        sourceCityId: int,
        destinationCityId: int,
        resourceTypeId: int,
        amount: int,
        hour: int,
    ) -> AjaxResponse:
        """Purchase / create an additional trade route slot and configure it."""
        ...


# ---------------------------------------------------------------------------
# Military Advisor
# ---------------------------------------------------------------------------


class OccupiedLocation:
    """Represents an occupied town or blockaded port listed by the Military Advisor."""

    townName: str
    townId: Optional[int]
    level: Optional[int]
    islandName: Optional[str]
    islandCoords: Optional[Tuple[int, int]]
    islandId: Optional[int]
    resourceName: Optional[str]
    actionHref: Optional[str]

    def __init__(
        self,
        *,
        townName: str,
        townId: Optional[int],
        level: Optional[int],
        islandName: Optional[str],
        islandCoords: Optional[Tuple[int, int]],
        islandId: Optional[int],
        resourceName: Optional[str],
        actionHref: Optional[str],
    ) -> None:
        self.townName = townName
        self.townId = townId
        self.level = level
        self.islandName = islandName
        self.islandCoords = islandCoords
        self.islandId = islandId
        self.resourceName = resourceName
        self.actionHref = actionHref


class CombatInProgressEntry:
    """Single active combat row shown under ``Current battles``."""

    combatId: Optional[int]
    title: str
    href: Optional[str]

    def __init__(
        self,
        *,
        combatId: Optional[int],
        title: str,
        href: Optional[str],
    ) -> None:
        self.combatId = combatId
        self.title = title
        self.href = href


def _parse_occupied_table(raw_html: Any) -> List[OccupiedLocation]:
    """Parse ``js_MilitaryMovementsOccupied{Cities|Ports}Table`` HTML snippets."""
    if not raw_html or not isinstance(raw_html, str):
        return []
    soup = make_soup(raw_html)
    entries: List[OccupiedLocation] = []
    for tr in soup.select("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 4 or any(td.get("colspan") for td in tds):
            continue
        town_a = tds[0].find("a")
        town_name = tds[0].get_text(" ", strip=True)
        town_id = (
            parse_query_int(str(town_a["href"]), "selectCity")
            or parse_query_int(str(town_a["href"]), "cityId")
            if town_a and town_a.get("href")
            else None
        )
        level = _parse_pure_int(tds[1].get_text(" ", strip=True))
        isl_a = tds[2].find("a")
        isl_text = tds[2].get_text(" ", strip=True)
        isl_name, isl_coords = _extract_coords(isl_text)
        isl_id = (
            parse_query_int(str(isl_a["href"]), "islandId")
            if isl_a and isl_a.get("href")
            else None
        )
        res_img = tds[3].find("img")
        res_name = (
            str(res_img.get("title") or res_img.get("alt"))
            if res_img and (res_img.get("title") or res_img.get("alt"))
            else (tds[3].get_text(" ", strip=True) or None)
        )
        action_a = tds[4].find("a") if len(tds) >= 5 else None
        action_href = (
            str(action_a["href"]) if action_a and action_a.get("href") else None
        )
        entries.append(
            OccupiedLocation(
                townName=town_name,
                townId=town_id,
                level=level,
                islandName=isl_name,
                islandCoords=isl_coords,
                islandId=isl_id,
                resourceName=res_name,
                actionHref=action_href,
            )
        )
    return entries


class MilitaryTable:
    """Parsed active army and fleet movements from the military advisor."""

    view: "MilitaryView"
    rows: List[MilitaryMovement]

    def __init__(
        self,
        view: "MilitaryView",
        militaryMovements: Union[List[dict], dict],
    ) -> None:
        """Parse military movement dictionaries into :class:`MilitaryMovement` rows."""
        self.view = view
        self.__militaryMovements = militaryMovements

        items = (
            list(militaryMovements.values())
            if isinstance(militaryMovements, dict)
            else list(militaryMovements or [])
        )
        self.rows = []
        for militaryMovement in items:
            if not isinstance(militaryMovement, dict) or "event" not in militaryMovement:
                continue
            event = militaryMovement["event"]
            movementId = int(event["id"])
            movement_type = event["type"]
            missionId = int(event["mission"])
            missionText = event["missionText"]
            missionState = parse_int(event.get("missionState"))
            missionIconClass = str(event.get("missionIconClass") or "")
            isReturning = bool(event.get("isReturning", False))
            isFleetReturning = bool(event.get("isFleetReturning", False))
            isInFight = bool(event.get("isInFight", False))
            isCombatant = bool(event.get("isCombatant", False))
            isOwnLoading = bool(event.get("isFirstOwnLoadingQueueEvent", False))
            isLoadingAccelerated = bool(event.get("loadingAccelerated", False))
            canAbort = bool(event.get("canAbort", False))
            canRetreat = bool(event.get("canRetreat", False))

            endTime = datetime.fromtimestamp(int(militaryMovement["eventTime"]))
            eventDateText = str(militaryMovement.get("eventDate") or "")
            isUnitsHidden = bool(militaryMovement.get("hideUnits", False))

            army = militaryMovement.get("army") or {}
            fleet = militaryMovement.get("fleet") or {}
            units = []
            for entry in [*army.get("units", []), *fleet.get("ships", [])]:
                unit_template = Units.getUnitByCssClass(entry.get("cssClass", ""))
                amount = parse_int(entry.get("amount"))
                if unit_template is not None and amount is not None:
                    units.append(unit_template(amount))

            if units:
                totalUnits = sum(u.count for u in units)
            else:
                totalUnits = (parse_int(army.get("amount")) or 0) + (
                    parse_int(fleet.get("amount")) or 0
                )

            totalTransportersAndFreighters = sum(
                u.count for u in units if u.cssClass in ["ship_transport", "ship_freighter"]
            )

            resources = []
            for resource in militaryMovement.get("resources") or []:
                css_class = (resource.get("cssClass") or "").replace("resource_icon", "").strip()
                resource_template = Resources.getResourceByCssClass(css_class)
                amount = parse_int(resource.get("amount"))
                if resource_template is not None and amount is not None:
                    resources.append(resource_template(amount))
            totalResources = sum(r.count for r in resources)

            isOwnArmyOrFleet = bool(militaryMovement.get("isOwnArmyOrFleet", False))
            isSameAlliance = bool(militaryMovement.get("isSameAlliance", False))
            isHostile = bool(militaryMovement.get("isHostile", False))
            tritonEngines = bool(militaryMovement.get("tritonEngines", False))

            origin_raw = militaryMovement.get("origin") or {}
            target_raw = militaryMovement.get("target") or {}
            origin = _parse_movement_node(origin_raw)
            target = _parse_movement_node(target_raw)
            targetHasBarbarianFleet = bool(target_raw.get("hasBarbarianFleet", False))

            self.rows.append(
                MilitaryMovement(
                    movementId,
                    movement_type,
                    missionId,
                    missionText,
                    isReturning,
                    isFleetReturning,
                    isInFight,
                    isCombatant,
                    isOwnLoading,
                    isLoadingAccelerated,
                    canAbort,
                    canRetreat,
                    endTime,
                    isUnitsHidden,
                    totalUnits,
                    units,
                    totalTransportersAndFreighters,
                    totalResources,
                    resources,
                    isOwnArmyOrFleet,
                    isSameAlliance,
                    isHostile,
                    tritonEngines,
                    origin,
                    target,
                    missionState=missionState,
                    missionIconClass=missionIconClass,
                    eventDateText=eventDateText,
                    targetHasBarbarianFleet=targetHasBarbarianFleet,
                )
            )


class MilitaryView:
    """Military advisor view holding active movements, battles, occupied locations, and tabs."""

    client: "Client"
    militaryTable: MilitaryTable
    currentTimestamp: Optional[int]
    currentTime: Optional[datetime]
    hasBarbarianFleet: bool
    premiumTroopInfo: Dict[str, Any]
    troopMovementsCount: int
    combatReportsCount: int
    movementFilterTypes: List[str]
    combatsInProgress: List[CombatInProgressEntry]
    occupiedCitiesCount: int
    maxOccupiedCities: int
    occupiedCities: List[OccupiedLocation]
    occupiedPortsCount: int
    maxOccupiedPorts: int
    occupiedPorts: List[OccupiedLocation]

    def __init__(
        self,
        client: "Client",
        militaryAndFleetMovements: Union[List[dict], dict],
        updateTemplateData: dict,
        *,
        viewData: Optional[Union[str, AjaxResponse]] = None,
        viewScriptParams: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the military advisor view from movement, script, and HTML payloads."""
        self.client = client
        self.__military_and_fleet_movements = militaryAndFleetMovements
        self.__update_template_data = updateTemplateData or {}

        resp: Optional[AjaxResponse] = None
        soup: Optional[BeautifulSoup] = None
        if viewData is not None:
            resp, soup = parse_view_payload(viewData)
            if not self.__update_template_data and resp.template_data:
                self.__update_template_data = resp.template_data
            if viewScriptParams is None and resp.view_script_params:
                viewScriptParams = resp.view_script_params

        self._military_response = resp
        vsp = viewScriptParams if isinstance(viewScriptParams, dict) else {}

        cur_ts = parse_int(vsp.get("currentTime"))
        self.currentTimestamp = cur_ts
        self.currentTime = datetime.fromtimestamp(cur_ts) if cur_ts and cur_ts > 0 else None
        self.hasBarbarianFleet = bool(vsp.get("hasBarbarianFleet", False))
        self.premiumTroopInfo = (
            dict(vsp["premiumTroopInfo"])
            if isinstance(vsp.get("premiumTroopInfo"), dict)
            else {}
        )

        self.militaryTable = MilitaryTable(self, militaryAndFleetMovements)

        tab_counts = _parse_tab_counts(soup) if soup is not None else {}
        self.troopMovementsCount = tab_counts.get(
            "js_tab_militaryAdvisor", len(self.militaryTable.rows)
        )
        self.combatReportsCount = tab_counts.get("js_tab_militaryAdvisorCombatList", 0)
        self.movementFilterTypes = (
            [
                str(el["data-filter"])
                for el in soup.select("#militaryMovementsFleetMovementsFilters .missionFilter[data-filter]")
            ]
            if soup is not None
            else []
        )

        self.combatsInProgress = []
        combat_td = self.__update_template_data.get("js_MilitaryMovementsCombatsInProgress")
        combat_hidden = isinstance(combat_td, dict) and "invisible" in str(
            combat_td.get("addClass") or ""
        )
        if not combat_hidden:
            combat_rows: List[Tag] = []
            if isinstance(combat_td, str) and combat_td.strip():
                combat_rows = make_soup(combat_td).select("tr")
            elif soup is not None:
                combat_rows = soup.select("#js_MilitaryMovementsCombatList tr")
            for tr in combat_rows:
                if tr.select_one("th") or tr.select_one("td[colspan]"):
                    continue
                link = tr.find("a")
                href = str(link["href"]) if link and link.get("href") else None
                cid = parse_query_int(href, "combatId") if href else None
                title = tr.get_text(" ", strip=True)
                if title:
                    self.combatsInProgress.append(
                        CombatInProgressEntry(combatId=cid, title=title, href=href)
                    )

        cities_html = self.__update_template_data.get(
            "js_MilitaryMovementsOccupiedCitiesTable"
        )
        self.occupiedCities = _parse_occupied_table(cities_html)
        c_cnt, c_max = (
            _parse_pair_header_count(soup, "Occupied Cities")
            if soup is not None
            else (None, None)
        )
        self.occupiedCitiesCount = c_cnt if c_cnt is not None else len(self.occupiedCities)
        self.maxOccupiedCities = c_max or 0

        ports_html = self.__update_template_data.get(
            "js_MilitaryMovementsOccupiedPortsTable"
        )
        self.occupiedPorts = _parse_occupied_table(ports_html)
        p_cnt, p_max = (
            _parse_pair_header_count(soup, "Occupied Ports")
            if soup is not None
            else (None, None)
        )
        self.occupiedPortsCount = p_cnt if p_cnt is not None else len(self.occupiedPorts)
        self.maxOccupiedPorts = p_max or 0

    async def getCombatReports(self, offset: int = 0) -> "CombatReportsView":
        """Open the Military Advisor Combat Reports tab (read-only)."""
        return await self.client.getCombatReportsView(offset=offset)

    async def getWars(self) -> "WarsView":
        """Open the Military Advisor Gauntlet Wars tab (read-only)."""
        return await self.client.getWarsView()

    async def abortMovement(self, movementId: int) -> AjaxResponse:
        """Abort or recall a friendly movement where ``canAbort`` is ``True``."""
        target_id = int(movementId)
        movement = next(
            (r for r in self.militaryTable.rows if r.movementId == target_id),
            None,
        )
        if movement is None:
            raise ValueError(f"Movement {target_id} was not found in MilitaryView")
        if not movement.canAbort:
            raise ValueError(
                f"Movement {target_id} ({movement.missionText}) cannot be aborted"
            )
        return await self.client.post_action(
            params={
                "action": "transportOperations",
                "function": "abortFleetOperation",
                "eventId": str(target_id),
                "oldView": "militaryAdvisor",
                "activeTab": "militaryMovements",
                "backgroundView": "city",
                "templateView": "militaryAdvisor",
                "actionRequest": "REQUESTID",
                "ajax": "1",
            },
            metadata={"ambrosia_cost": 0, "movementId": target_id},
            action_name=f"MilitaryView.abortMovement({target_id})",
        )

    async def retreatMovement(self, movementId: int) -> AjaxResponse:
        """Withdraw units from combat or deployment where ``canRetreat`` is ``True``."""
        ...

    async def accelerateLoading(self, movementId: int) -> AjaxResponse:
        """Accelerate fleet loading using Ambrosia."""
        ...

    async def releaseOccupiedCity(self, cityId: int) -> AjaxResponse:
        """Withdraw occupying forces from an occupied city."""
        ...

    async def releaseOccupiedPort(self, cityId: int) -> AjaxResponse:
        """Lift a blockade from an occupied port."""
        ...


class CombatReportEntry:
    """Single summary row on the Military Advisor Combat Reports tab."""

    combatId: Optional[int]
    date: Optional[datetime]
    subject: str
    isWon: Optional[bool]
    isNew: bool
    href: Optional[str]

    def __init__(
        self,
        *,
        combatId: Optional[int],
        date: Optional[datetime],
        subject: str,
        isWon: Optional[bool],
        isNew: bool,
        href: Optional[str],
    ) -> None:
        self.combatId = combatId
        self.date = date
        self.subject = subject
        self.isWon = isWon
        self.isNew = isNew
        self.href = href


class CombatReportsView:
    """Military Advisor Combat Reports tab view (``view=militaryAdvisorCombatList``)."""

    client: "Client"
    reports: List[CombatReportEntry]
    troopMovementsCount: int
    combatReportsCount: int

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse combat report summary rows and tab counts."""
        self.client = client
        resp, soup = parse_view_payload(viewData)
        self._combat_reports_response = resp
        self.reports = []

        tab_counts = _parse_tab_counts(soup)
        self.troopMovementsCount = tab_counts.get("js_tab_militaryAdvisor", 0)
        self.combatReportsCount = tab_counts.get("js_tab_militaryAdvisorCombatList", 0)

        for tr in soup.select("#mainview table tr"):
            if tr.select_one("th") or tr.select_one("td[colspan]"):
                continue
            link = tr.select_one("a[href*='combatId']")
            if link is None:
                continue
            href = str(link["href"])
            combat_id = parse_query_int(href, "combatId")
            tr_classes = set(tr.get("class") or [])
            tds = tr.find_all("td")
            parsed_date = next(
                (d for d in (_parse_date(td.get_text(" ", strip=True)) for td in tds) if d),
                None,
            )
            is_won: Optional[bool] = None
            if tr_classes & {"won", "green"} or tr.select_one(".won"):
                is_won = True
            elif tr_classes & {"lost", "red"} or tr.select_one(".lost"):
                is_won = False
            subject = link.get_text(" ", strip=True)
            if not subject:
                type_img = tds[1].select_one("img") if len(tds) > 1 else None
                fight_type = (
                    str(type_img.get("title") or type_img.get("alt") or "").strip()
                    if type_img is not None
                    else ""
                )
                town = tds[4].get_text(" ", strip=True) if len(tds) > 4 else ""
                owner = tds[5].get_text(" ", strip=True) if len(tds) > 5 else ""
                parts = [p for p in (fight_type, town) if p]
                subject = ": ".join(parts) if len(parts) == 2 else " ".join(parts)
                if owner:
                    subject = f"{subject} ({owner})" if subject else owner
            self.reports.append(
                CombatReportEntry(
                    combatId=combat_id,
                    date=parsed_date,
                    subject=subject,
                    isWon=is_won,
                    isNew=bool(tr_classes & {"new", "unread", "bold"}),
                    href=href,
                )
            )

    async def getMovements(self) -> MilitaryView:
        """Switch back to the Military Advisor Troop Movements tab."""
        return await self.client.getMilitaryView()

    async def openDetailedReport(self, reportId: int) -> AjaxResponse:
        """Fetch the detailed battle report view for ``reportId``."""
        rid = int(reportId)
        entry = next((r for r in self.reports if r.combatId == rid), None)
        params: Dict[str, str] = {
            "view": "militaryAdvisorReportView",
            "combatId": str(rid),
            "activeTab": "combatReports",
            "backgroundView": "city",
            "templateView": "militaryAdvisorReportView",
            "actionRequest": "REQUESTID",
            "ajax": "1",
        }
        if entry is not None and entry.href:
            parsed = parse_query_params(entry.href)
            params.update(parsed)
        return await self.client.post_ajax(params=params)

    async def deleteReport(self, reportId: int) -> AjaxResponse:
        """Delete a single combat report."""
        return await self.deleteReports([int(reportId)])

    async def deleteReports(self, reportIds: List[int]) -> AjaxResponse:
        """Delete multiple selected combat reports."""
        ids = [int(rid) for rid in reportIds]
        if not ids:
            raise ValueError("Must specify at least one combat report ID to delete")
        payload: Dict[str, str] = {
            "start": "0",
            "action": "MilitaryAction",
            "function": "modifyCombatReport",
            "command": "delete",
        }
        for rid in ids:
            payload[f"combatId[{rid}]"] = "1"
        return await self.client.post_action(
            payloadPost=payload,
            params={
                "backgroundView": "city",
                "templateView": "militaryAdvisorCombatList",
                "actionRequest": "REQUESTID",
                "ajax": "1",
            },
            metadata={"ambrosia_cost": 0, "reportIds": ids},
            action_name="CombatReportsView.deleteReports",
        )

    async def archiveReport(self, reportId: int) -> AjaxResponse:
        """Archive a combat report into the permanent archive (requires Premium / Ambrosia; stub)."""
        ...


class WarEntry:
    """Single active or concluded war entry on the Gauntlet Wars tab."""

    title: str
    warId: Optional[int]
    href: Optional[str]
    rawRowText: str

    def __init__(
        self,
        *,
        title: str,
        warId: Optional[int],
        href: Optional[str],
        rawRowText: str,
    ) -> None:
        self.title = title
        self.warId = warId
        self.href = href
        self.rawRowText = rawRowText


class WarsView:
    """Military Advisor Gauntlet Wars view (``militaryAdvisorWarList`` & concluded wars)."""

    client: "Client"
    personalWars: List[WarEntry]
    allianceWars: List[WarEntry]
    troopMovementsCount: int
    combatReportsCount: int
    oldWarsHref: Optional[str]
    oldAllyWarsHref: Optional[str]

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse active or concluded Gauntlet Wars sections."""
        self.client = client
        resp, soup = parse_view_payload(viewData)
        self._wars_response = resp
        self.personalWars = []
        self.allianceWars = []

        tab_counts = _parse_tab_counts(soup)
        self.troopMovementsCount = tab_counts.get("js_tab_militaryAdvisor", 0)
        self.combatReportsCount = tab_counts.get("js_tab_militaryAdvisorCombatList", 0)

        for box in soup.select("#mainview .contentBox01h"):
            header = box.select_one("h3.header")
            header_text = header.get_text(" ", strip=True) if header else ""
            lower_hdr = header_text.lower()
            target_list = (
                self.allianceWars
                if "alliance" in lower_hdr
                else (self.personalWars if "war" in lower_hdr else None)
            )
            if target_list is None:
                continue
            for tr in box.select("table tr"):
                if tr.select_one("th") or tr.select_one("td[colspan]"):
                    continue
                link = tr.find("a")
                href = str(link["href"]) if link and link.get("href") else None
                war_id = parse_query_int(href, "warId") if href else None
                row_text = tr.get_text(" ", strip=True)
                if row_text:
                    target_list.append(
                        WarEntry(
                            title=link.get_text(" ", strip=True) if link else row_text,
                            warId=war_id,
                            href=href,
                            rawRowText=row_text,
                        )
                    )

        old_w = soup.select_one("a[href*='militaryAdvisorOldWars']")
        old_aw = soup.select_one("a[href*='militaryAdvisorOldAllyWars']")
        self.oldWarsHref = str(old_w["href"]) if old_w and old_w.get("href") else None
        self.oldAllyWarsHref = str(old_aw["href"]) if old_aw and old_aw.get("href") else None

    async def getOldWars(self) -> "WarsView":
        """Load the player's concluded Gauntlet Wars list (read-only)."""
        resp = await self.client.get_ajax(params={"view": "militaryAdvisorOldWars"})
        if resp.view_html is None:
            raise ValueError("Missing view HTML in concluded wars response")
        return WarsView(self.client, resp)

    async def getOldAllyWars(self) -> "WarsView":
        """Load the alliance's concluded Gauntlet Wars list (read-only)."""
        resp = await self.client.get_ajax(params={"view": "militaryAdvisorOldAllyWars"})
        if resp.view_html is None:
            raise ValueError("Missing view HTML in concluded alliance wars response")
        return WarsView(self.client, resp)


# ---------------------------------------------------------------------------
# Research Advisor
# ---------------------------------------------------------------------------


class ResearchArea:
    """Summary of one of the 5 research branches (Seafaring, Economy, Science, Military, Mythology)."""

    index: int
    key: str
    name: str
    isActiveTab: bool
    nextResearchName: str
    nextResearchTooltipName: str
    nextResearchDescription: str
    nextResearchCost: Optional[int]
    hasEnoughPoints: bool
    isAvailable: bool
    isMaxed: bool
    statusText: str
    availableAt: Optional[datetime]
    remainingSeconds: Optional[int]
    ajaxHref: Optional[str]

    def __init__(
        self,
        *,
        index: int,
        key: str,
        name: str,
        isActiveTab: bool,
        nextResearchName: str,
        nextResearchTooltipName: str,
        nextResearchDescription: str,
        nextResearchCost: Optional[int],
        hasEnoughPoints: bool,
        isAvailable: bool,
        isMaxed: bool,
        statusText: str,
        availableAt: Optional[datetime],
        remainingSeconds: Optional[int],
        ajaxHref: Optional[str],
    ) -> None:
        self.index = index
        self.key = key
        self.name = name
        self.isActiveTab = isActiveTab
        self.nextResearchName = nextResearchName
        self.nextResearchTooltipName = nextResearchTooltipName
        self.nextResearchDescription = nextResearchDescription
        self.nextResearchCost = nextResearchCost
        self.hasEnoughPoints = hasEnoughPoints
        self.isAvailable = isAvailable
        self.isMaxed = isMaxed
        self.statusText = statusText
        self.availableAt = availableAt
        self.remainingSeconds = remainingSeconds
        self.ajaxHref = ajaxHref


class ResearchEntry:
    """Single research entry within an area's tech list."""

    id: Optional[int]
    name: str
    isExplored: bool
    isExplorable: bool
    isSelected: bool
    href: Optional[str]

    def __init__(
        self,
        *,
        researchId: Optional[int],
        name: str,
        isExplored: bool,
        isExplorable: bool,
        isSelected: bool,
        href: Optional[str],
    ) -> None:
        self.id = researchId
        self.name = name
        self.isExplored = isExplored
        self.isExplorable = isExplorable
        self.isSelected = isSelected
        self.href = href


class ResearchPrecondition:
    """Prerequisite technology or building requirement for the selected research."""

    name: str
    requirementType: str
    isSatisfied: bool
    href: Optional[str]

    def __init__(
        self,
        *,
        name: str,
        requirementType: str,
        isSatisfied: bool,
        href: Optional[str],
    ) -> None:
        self.name = name
        self.requirementType = requirementType
        self.isSatisfied = isSatisfied
        self.href = href


class ResearchDetail:
    """Currently inspected research details from the right-hand Research Advisor panel."""

    id: Optional[int]
    areaKey: str
    name: str
    description: str
    cost: Optional[int]
    timeNeeded: str
    hasEnoughPoints: bool
    canResearch: bool
    researchHref: Optional[str]
    buttonText: str
    preconditions: List[ResearchPrecondition]

    def __init__(
        self,
        *,
        researchId: Optional[int],
        areaKey: str,
        name: str,
        description: str,
        cost: Optional[int],
        timeNeeded: str,
        hasEnoughPoints: bool,
        canResearch: bool,
        researchHref: Optional[str],
        buttonText: str,
        preconditions: List[ResearchPrecondition],
    ) -> None:
        self.id = researchId
        self.areaKey = areaKey
        self.name = name
        self.description = description
        self.cost = cost
        self.timeNeeded = timeNeeded
        self.hasEnoughPoints = hasEnoughPoints
        self.canResearch = canResearch
        self.researchHref = researchHref
        self.buttonText = buttonText
        self.preconditions = preconditions


class ResearchView:
    """View model for the Research Advisor (``view=researchAdvisor``)."""

    client: "Client"
    currentAreaKey: str
    currentAreaName: str
    scientists: int
    researchPoints: int
    researchPointsPerHour: float
    productionBreakdown: Dict[str, float]
    areas: List[ResearchArea]
    researches: List[ResearchEntry]
    selectedResearch: Optional[ResearchDetail]

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse Research Advisor point totals, 5 branch summaries, and selected tech tree."""
        self.client = client
        resp, soup = parse_view_payload(viewData)
        self._research_response = resp
        td = resp.template_data

        self.currentAreaName = tmpl_text(resp, "js_researchAdvisorCurrResearchType") or (
            soup.select_one("#js_researchAdvisorCurrResearchType").get_text(" ", strip=True)
            if soup.select_one("#js_researchAdvisorCurrResearchType")
            else ""
        )

        sci_raw = tmpl_text(resp, "js_researchAdvisorScientists")
        if not sci_raw and soup.select_one("#js_researchAdvisorScientists"):
            sci_raw = soup.select_one("#js_researchAdvisorScientists").get_text(" ", strip=True)
        self.scientists = parse_int(sci_raw) or 0

        pts_raw = tmpl_text(resp, "js_researchAdvisorPoints")
        if not pts_raw and soup.select_one("#js_researchAdvisorPoints"):
            pts_raw = soup.select_one("#js_researchAdvisorPoints").get_text(" ", strip=True)
        self.researchPoints = parse_int(pts_raw) or 0

        rate_raw = tmpl_text(resp, "js_researchAdvisorTime")
        if not rate_raw and soup.select_one("#js_researchAdvisorTime"):
            rate_raw = soup.select_one("#js_researchAdvisorTime").get_text(" ", strip=True)
        self.researchPointsPerHour = parse_float(rate_raw) or 0.0

        self.productionBreakdown = {}
        for tr in soup.select("#js_infoResearchAdvisorBreakdownTooltip table.breakdown_table tr"):
            tds = tr.find_all("td")
            if len(tds) >= 2:
                label = tds[0].get_text(" ", strip=True).rstrip(":")
                val = parse_float(tds[1].get_text(" ", strip=True).replace(" ", ""))
                if label and val is not None:
                    self.productionBreakdown[label] = val

        self.areas = []
        self.currentAreaKey = ""
        idx = 0
        while True:
            type_key = f"js_researchAdvisorChangeResearchType{idx}"
            if type_key not in td and soup.find(id=type_key) is None:
                break
            type_entry = td.get(type_key)
            ajax_req = (
                str(type_entry.get("ajaxrequest") or "")
                if isinstance(type_entry, dict)
                else ""
            )
            area_key = parse_query_str(ajax_req, "researchType") or str(idx)
            type_classes = (
                str(type_entry.get("class") or "").split()
                if isinstance(type_entry, dict)
                else []
            )
            active_cls_entry = td.get(f"js_researchAdvisorTypeActiveClass{idx}")
            active_classes = (
                str(active_cls_entry.get("class") or "").split()
                if isinstance(active_cls_entry, dict)
                else []
            )
            is_active = "active" in type_classes or "active" in active_classes
            if is_active:
                self.currentAreaKey = area_key

            area_name = tmpl_text(resp, f"js_researchAdvisorChangeResearchTypeTxt{idx}")
            next_name = tmpl_text(resp, f"js_researchAdvisorNextResearchName{idx}")
            tooltip_name = tmpl_text(resp, f"js_researchAdvisorNextResearchTooltipName{idx}")
            tooltip_desc = tmpl_text(
                resp, f"js_researchAdvisorNextResearchTooltipShortDesc{idx}"
            )
            cost_entry = td.get(f"js_researchAdvisorNextResearchCost{idx}")
            cost_str = (
                str(cost_entry.get("text") or "")
                if isinstance(cost_entry, dict)
                else str(cost_entry or "")
            )
            next_cost = _parse_pure_int(cost_str)
            cost_red = isinstance(cost_entry, dict) and cost_entry.get("addClass") == "red"
            has_enough = next_cost is not None and not cost_red

            prog_txt = tmpl_text(resp, f"js_researchAdvisorProgressTxt{idx}")
            pb_raw = td.get(f"js_researchAdvisorProgressbar{idx}")
            pb_dict = pb_raw.get("progressbar") if isinstance(pb_raw, dict) else None
            avail_dt, _, rem_secs = _parse_countdown_entry(pb_dict)
            if not prog_txt:
                prog_el = soup.find(id=f"js_researchAdvisorProgressTxt{idx}")
                prog_txt = prog_el.get_text(" ", strip=True) if prog_el else ""
            if not prog_txt and rem_secs is not None:
                prog_txt = "Available in"

            is_maxed = "maximum" in prog_txt.lower() or (
                not next_name and next_cost is None
            )
            is_available = prog_txt.lower() == "available" or (
                has_enough and not is_maxed and rem_secs is None
            )

            link_el = soup.find(id=type_key)
            href = str(link_el["href"]) if link_el and link_el.get("href") else ajax_req or None

            self.areas.append(
                ResearchArea(
                    index=idx,
                    key=area_key,
                    name=area_name,
                    isActiveTab=is_active,
                    nextResearchName=next_name,
                    nextResearchTooltipName=tooltip_name,
                    nextResearchDescription=tooltip_desc,
                    nextResearchCost=next_cost,
                    hasEnoughPoints=has_enough,
                    isAvailable=is_available,
                    isMaxed=is_maxed,
                    statusText=prog_txt,
                    availableAt=avail_dt,
                    remainingSeconds=rem_secs,
                    ajaxHref=href,
                )
            )
            idx += 1

        self.researches = []
        self.selectedResearch = None

        load_js = td.get("load_js")
        raw_params: Any = None
        if isinstance(load_js, dict) and load_js.get("params"):
            raw_params = load_js["params"]
        elif td.get("new_js_params"):
            raw_params = td["new_js_params"]
        params_obj: Dict[str, Any] = {}
        if raw_params:
            try:
                loaded = (
                    json.loads(raw_params) if isinstance(raw_params, str) else raw_params
                )
                if isinstance(loaded, dict):
                    params_obj = loaded
            except (TypeError, json.JSONDecodeError):
                params_obj = {}

        selected_id: Optional[int] = None
        curr_tree = params_obj.get("currResearchType")
        if isinstance(curr_tree, dict):
            for r_name, meta in curr_tree.items():
                if not isinstance(meta, dict):
                    continue
                li_classes = str(meta.get("liClass") or "").split()
                href = str(meta.get("aHref") or "") or None
                rid = parse_query_int(href, "researchId") if href else None
                is_selected = "selected" in li_classes
                if is_selected:
                    selected_id = rid
                self.researches.append(
                    ResearchEntry(
                        researchId=rid,
                        name=str(r_name),
                        isExplored="explored" in li_classes,
                        isExplorable="explorable" in li_classes,
                        isSelected=is_selected,
                        href=href,
                    )
                )

        cons_link = td.get("js_researchAdvisorConservationLink")
        research_href: Optional[str] = None
        cons_area: Optional[str] = None
        if isinstance(cons_link, dict):
            research_href = str(cons_link["href"]) if cons_link.get("href") else None
            data_meta = cons_link.get("data")
            if isinstance(data_meta, dict) and data_meta.get("value"):
                cons_area = str(data_meta["value"])
            if not cons_area and research_href:
                cons_area = parse_query_str(research_href, "type")
        if not self.currentAreaKey and cons_area:
            self.currentAreaKey = cons_area

        if params_obj.get("currResearchName"):
            raw_desc = str(params_obj.get("currResearchDesc") or "")
            desc_text = make_soup(raw_desc).get_text(" ", strip=True)
            cost = _parse_pure_int(str(params_obj.get("currResearchCosts") or ""))
            not_enough_txt = str(params_obj.get("currResearchPointsNotEnoughTxt") or "").strip()
            btn_state = str(params_obj.get("currResearchBtnState") or "").split()
            can_research = (
                "invisible" not in btn_state
                and "button_disabled" not in btn_state
                and bool(research_href)
            )

            preconditions: List[ResearchPrecondition] = []
            raw_pre = params_obj.get("currResearchPrecond")
            if isinstance(raw_pre, dict):
                for p_name, p_meta in raw_pre.items():
                    if not isinstance(p_meta, dict):
                        continue
                    preconditions.append(
                        ResearchPrecondition(
                            name=str(p_name),
                            requirementType=str(p_meta.get("type") or ""),
                            isSatisfied="arrow_ok" in str(p_meta.get("spanClass") or "").split(),
                            href=str(p_meta["aHref"]) if p_meta.get("aHref") else None,
                        )
                    )

            self.selectedResearch = ResearchDetail(
                researchId=selected_id,
                areaKey=self.currentAreaKey or cons_area or "",
                name=str(params_obj.get("currResearchName") or ""),
                description=desc_text,
                cost=cost,
                timeNeeded=str(params_obj.get("currResearchTimeNeeded") or ""),
                hasEnoughPoints=(not not_enough_txt) and cost is not None,
                canResearch=can_research,
                researchHref=research_href,
                buttonText=str(params_obj.get("currResearchBtnTxt") or ""),
                preconditions=preconditions,
            )

    def getArea(self, keyOrIndex: Union[str, int]) -> Optional[ResearchArea]:
        """Look up a research area by key (e.g. ``'economy'``) or numeric index."""
        if isinstance(keyOrIndex, int):
            return next((a for a in self.areas if a.index == keyOrIndex), None)
        return next(
            (a for a in self.areas if a.key == keyOrIndex or a.name == keyOrIndex),
            None,
        )

    def getResearch(self, idOrName: Union[int, str]) -> Optional[ResearchEntry]:
        """Look up a research entry in the current area by numeric ID or name."""
        if isinstance(idOrName, int):
            return next((r for r in self.researches if r.id == idOrName), None)
        return next((r for r in self.researches if r.name == idOrName), None)

    async def selectArea(self, researchType: str) -> "ResearchView":
        """Switch to another research branch (read-only)."""
        return await self.client.getResearchView(researchType=researchType)

    async def selectResearch(
        self,
        researchId: int,
        researchType: Optional[str] = None,
    ) -> "ResearchView":
        """Inspect a specific technology in the Research Advisor (read-only)."""
        return await self.client.getResearchView(
            researchType=researchType or self.currentAreaKey or None,
            researchId=researchId,
        )

    async def loadAllAreas(self) -> Dict[str, List[ResearchEntry]]:
        """Fetch tech lists for every research branch in read-only mode."""
        result: Dict[str, List[ResearchEntry]] = {}
        if self.currentAreaKey:
            result[self.currentAreaKey] = list(self.researches)
        for area in self.areas:
            if area.key and area.key not in result:
                view = await self.selectArea(area.key)
                result[area.key] = list(view.researches)
        return result

    async def doResearch(self, researchType: Optional[str] = None) -> AjaxResponse:
        """Complete the currently available technology in ``researchType``."""
        ...


# ---------------------------------------------------------------------------
# Diplomacy Advisor
# ---------------------------------------------------------------------------


class DiplomacyMessage:
    """Single message, circular, or treaty offer row in Diplomacy Advisor."""

    id: int
    isNew: bool
    partnerId: Optional[int]
    partnerName: str
    partnerFlagTag: str
    subject: str
    isCircular: bool
    isTreatyOffer: bool
    cityName: Optional[str]
    cityCoords: Optional[Tuple[int, int]]
    cityId: Optional[int]
    islandId: Optional[int]
    date: Optional[datetime]
    bodyText: str
    bodyHtml: str
    answerHref: Optional[str]
    replyAllHref: Optional[str]
    acceptHref: Optional[str]
    declineHref: Optional[str]
    ignoreHref: Optional[str]
    archiveHref: Optional[str]

    def __init__(
        self,
        *,
        messageId: int,
        isNew: bool,
        partnerId: Optional[int],
        partnerName: str,
        partnerFlagTag: str,
        subject: str,
        isCircular: bool,
        isTreatyOffer: bool,
        cityName: Optional[str],
        cityCoords: Optional[Tuple[int, int]],
        cityId: Optional[int],
        islandId: Optional[int],
        date: Optional[datetime],
        bodyText: str,
        bodyHtml: str,
        answerHref: Optional[str],
        replyAllHref: Optional[str],
        acceptHref: Optional[str],
        declineHref: Optional[str],
        ignoreHref: Optional[str],
        archiveHref: Optional[str],
    ) -> None:
        self.id = messageId
        self.isNew = isNew
        self.partnerId = partnerId
        self.partnerName = partnerName
        self.partnerFlagTag = partnerFlagTag
        self.subject = subject
        self.isCircular = isCircular
        self.isTreatyOffer = isTreatyOffer
        self.cityName = cityName
        self.cityCoords = cityCoords
        self.cityId = cityId
        self.islandId = islandId
        self.date = date
        self.bodyText = bodyText
        self.bodyHtml = bodyHtml
        self.answerHref = answerHref
        self.replyAllHref = replyAllHref
        self.acceptHref = acceptHref
        self.declineHref = declineHref
        self.ignoreHref = ignoreHref
        self.archiveHref = archiveHref


class TownCulturalStatus:
    """Per-town museum / cultural goods usage row on the Treaties tab."""

    cityName: str
    cityId: Optional[int]
    position: Optional[int]
    culturalGoods: int
    museumLevel: int
    museumHref: Optional[str]

    def __init__(
        self,
        *,
        cityName: str,
        cityId: Optional[int],
        position: Optional[int],
        culturalGoods: int,
        museumLevel: int,
        museumHref: Optional[str],
    ) -> None:
        self.cityName = cityName
        self.cityId = cityId
        self.position = position
        self.culturalGoods = culturalGoods
        self.museumLevel = museumLevel
        self.museumHref = museumHref


class DiplomacyTreatiesView:
    """Diplomacy Advisor Treaties tab (``view=diplomacyTreaty``)."""

    client: "Client"
    culturalGoodsUsed: int
    culturalGoodsMax: int
    towns: List[TownCulturalStatus]
    treaties: List[Dict[str, Any]]
    assignCulturalGoodsHref: Optional[str]

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse museum cultural goods summary and active treaties tables."""
        self.client = client
        resp, soup = parse_view_payload(viewData)
        self._treaties_response = resp

        used, max_cg = _parse_pair_header_count(soup, "Cultural goods agreement")
        self.culturalGoodsUsed = used or 0
        self.culturalGoodsMax = max_cg or 0
        self.towns = []
        self.treaties = []

        for tr in soup.select("table#culturalTreaties tr"):
            if tr.select_one("th") or tr.select_one("td[colspan]"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 3:
                continue
            link = tr.select_one("a[href]")
            href = str(link["href"]) if link and link.get("href") else None
            self.towns.append(
                TownCulturalStatus(
                    cityName=tds[0].get_text(" ", strip=True),
                    cityId=parse_query_int(href, "cityId") if href else None,
                    position=parse_query_int(href, "position") if href else None,
                    culturalGoods=parse_int(tds[1].get_text(" ", strip=True)) or 0,
                    museumLevel=parse_int(tds[2].get_text(" ", strip=True)) or 0,
                    museumHref=href,
                )
            )

        for tbl in soup.select("table"):
            if tbl.get("id") == "culturalTreaties":
                continue
            headers = [th.get_text(" ", strip=True) for th in tbl.select("th")]
            for tr in tbl.select("tr"):
                if tr.select_one("th") or tr.select_one("td[colspan]"):
                    continue
                tds = tr.find_all("td", recursive=False)
                if not tds:
                    continue
                cancel_a = tr.select_one("a[href*='cancelTreaty'], a[href*='deleteTreaty']")
                self.treaties.append(
                    {
                        "columns": [td.get_text(" ", strip=True) for td in tds],
                        "headers": headers,
                        "cancelHref": (
                            str(cancel_a["href"])
                            if cancel_a and cancel_a.get("href")
                            else None
                        ),
                    }
                )

        assign_a = soup.select_one("a[href*='culturalPossessions_assign']")
        self.assignCulturalGoodsHref = (
            str(assign_a["href"]) if assign_a and assign_a.get("href") else None
        )

    async def cancelTreaty(self, treatyHrefOrPlayerId: Union[str, int]) -> AjaxResponse:
        """Cancel a cultural goods or diplomatic treaty."""
        ...


class DiplomacyAgoraView:
    """Diplomacy Advisor Agora tab (``view=diplomacyIslandBoard``)."""

    client: "Client"
    selectedIslandId: Optional[int]
    islands: List[Dict[str, Any]]
    posts: List[Dict[str, Any]]
    newPostHref: Optional[str]

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse island Agora links, current island selection, and message board posts."""
        self.client = client
        resp, soup = parse_view_payload(viewData)
        self._agora_response = resp

        new_post = soup.select_one("a[href*='diplomacyIslandBoard'][href*='show=1']")
        self.newPostHref = (
            str(new_post["href"]) if new_post and new_post.get("href") else None
        )
        self.selectedIslandId = (
            parse_query_int(self.newPostHref, "islandId") if self.newPostHref else None
        )

        self.islands = []
        for a in soup.select("a[href*='diplomacyIslandBoard'][href*='islandId=']"):
            href = str(a["href"])
            if "show=1" in href:
                continue
            isl_id = parse_query_int(href, "islandId")
            if isl_id is None:
                continue
            self.islands.append(
                {
                    "islandId": isl_id,
                    "label": a.get_text(" ", strip=True),
                    "href": href,
                }
            )

        self.posts = []
        for post_el in soup.select(
            "#tab_diplomacyIslandBoard .contentBox01h, .post, .agoraPost, table.table01 tr.entry"
        ):
            if post_el.select_one("form.newMessage") is not None:
                continue
            warning = post_el.select_one("p.warning.red_box")
            if warning is not None and post_el.select_one("h3.header .avatarName") is None:
                continue
            header_el = post_el.select_one("h3.header")
            content_el = post_el.select_one(".content")
            author_el = post_el.select_one("h3.header .avatarName")
            text = (
                content_el.get_text(" ", strip=True)
                if content_el is not None
                else post_el.get_text(" ", strip=True)
            )
            if text:
                entry: Dict[str, Any] = {"text": text}
                if author_el is not None:
                    entry["author"] = author_el.get_text(" ", strip=True)
                if header_el is not None:
                    entry["header"] = header_el.get_text(" ", strip=True)
                self.posts.append(entry)

    async def selectIsland(self, islandId: int) -> "DiplomacyAgoraView":
        """Switch to another island's Agora board (read-only)."""
        return await self.client.getDiplomacyAgoraView(islandId=islandId)

    async def createPost(
        self,
        islandId: int,
        message: str,
        *,
        subject: str = "",
    ) -> AjaxResponse:
        """Post a new message on the specified island Agora."""
        body = str(message)
        if not body.strip():
            raise ValueError("Agora post message cannot be empty")
        return await self.client.post_action(
            payloadPost={
                "action": "IslandScreen",
                "function": "postNewMessage",
                "islandId": str(int(islandId)),
                "subject": str(subject)[:50],
                "message": body[:1000],
            },
            params={
                "backgroundView": "city",
                "templateView": "diplomacyIslandBoard",
                "actionRequest": "REQUESTID",
                "ajax": "1",
            },
            metadata={"ambrosia_cost": 0, "islandId": int(islandId)},
            action_name="DiplomacyAgoraView.createPost",
        )

    async def deletePost(self, postId: int) -> AjaxResponse:
        """Delete a post authored by the player from the Agora."""
        ...


class DiplomacyAllianceInfoView:
    """Diplomacy Advisor Alliance Info sub-view (``view=diplomacyAllyInfo``)."""

    client: "Client"
    name: str
    tag: str
    memberCount: int
    foundingDate: Optional[datetime]
    placement: Optional[int]
    points: Optional[int]
    diplomaticInfluence: Optional[int]
    userRank: str
    circularHref: Optional[str]

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse alliance metadata table."""
        self.client = client
        resp, soup = parse_view_payload(viewData)
        self._ally_info_response = resp

        self.name = ""
        self.tag = ""
        self.memberCount = 0
        self.foundingDate = None
        self.placement = None
        self.points = None
        self.diplomaticInfluence = None
        self.userRank = ""
        circ = soup.select_one("a[href*='sendIKMessage'][href*='msgType=51']")
        self.circularHref = str(circ["href"]) if circ and circ.get("href") else None

        for tr in soup.select("table tr"):
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 2:
                continue
            label = tds[0].get_text(" ", strip=True).rstrip(":").lower()
            val_cell = tds[1]
            val_text = val_cell.get_text(" ", strip=True)
            if label == "name":
                # Strip nested 'Send circular message' anchor text; name lives in <b> when present
                bold = val_cell.find("b")
                if bold is not None:
                    raw_name = bold.get_text(" ", strip=True)
                else:
                    direct = " ".join(
                        str(s).strip()
                        for s in val_cell.find_all(string=True, recursive=False)
                        if str(s).strip()
                    )
                    raw_name = direct or val_text
                m_tag = re.search(r"\[([^\]]+)\]\s*$", raw_name)
                if m_tag:
                    self.tag = m_tag.group(1).strip()
                    self.name = raw_name[: m_tag.start()].strip()
                else:
                    self.name = raw_name
            elif label == "members":
                self.memberCount = parse_int(val_text) or 0
            elif "founding" in label:
                self.foundingDate = _parse_date(val_text)
            elif "placement" in label:
                m_place = re.search(r"(\d[\d,.]*)\s*\(([\d,.\s]+)\)", val_text)
                if m_place:
                    self.placement = parse_int(m_place.group(1))
                    self.points = parse_int(m_place.group(2))
                else:
                    self.placement = parse_int(val_text)
            elif "influence" in label:
                self.diplomaticInfluence = parse_int(val_text)
            elif "rank" in label:
                self.userRank = val_text


class DiplomacyAllianceMembersView:
    """Diplomacy Advisor Alliance Member List sub-view (``view=diplomacyAllyMemberlist``)."""

    client: "Client"
    members: List[Dict[str, Any]]

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse rows from ``table#allyMemberList``."""
        self.client = client
        resp, soup = parse_view_payload(viewData)
        self._members_response = resp
        self.members = []

        for tr in soup.select("table#allyMemberList tr"):
            if tr.select_one("th"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 5:
                continue
            city_links = [
                {
                    "name": a.get_text(" ", strip=True),
                    "cityId": parse_query_int(str(a["href"]), "selectCity"),
                    "islandId": parse_query_int(str(a["href"]), "islandId"),
                }
                for a in tds[2].select("a[href]")
                if a.get("href")
            ]
            msg_a = tds[5].select_one("a[href*='sendIKMessage']") if len(tds) >= 6 else None
            self.members.append(
                {
                    "lastAction": _parse_date(tds[0].get_text(" ", strip=True)),
                    "name": tds[1].get_text(" ", strip=True),
                    "cities": city_links,
                    "rank": tds[3].get_text(" ", strip=True),
                    "points": parse_int(tds[4].get_text(" ", strip=True)) or 0,
                    "playerId": (
                        parse_query_int(str(msg_a["href"]), "receiverId")
                        if msg_a and msg_a.get("href")
                        else None
                    ),
                }
            )


class DiplomacyAllianceView:
    """Diplomacy Advisor Alliance tab (``view=diplomacyAlly``)."""

    client: "Client"
    circularHref: Optional[str]
    subforums: List[Dict[str, Any]]

    def __init__(self, client: "Client", viewData: Union[str, AjaxResponse]) -> None:
        """Parse alliance forum summary and sidebar links."""
        self.client = client
        resp, soup = parse_view_payload(viewData)
        self._ally_response = resp

        circ = soup.select_one("a[href*='sendIKMessage'][href*='msgType=51']")
        self.circularHref = str(circ["href"]) if circ and circ.get("href") else None
        self.subforums = []
        for tr in soup.select("table.topic_table tr"):
            if tr.select_one("th") or tr.select_one("td[colspan]"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) >= 2 and tr.get_text(" ", strip=True):
                self.subforums.append(
                    {"columns": [td.get_text(" ", strip=True) for td in tds]}
                )

    async def getInfo(self) -> DiplomacyAllianceInfoView:
        """Load the Alliance Information sub-view (read-only)."""
        return await self.client.getDiplomacyAllianceInfoView()

    async def getMembers(self) -> DiplomacyAllianceMembersView:
        """Load the Alliance Member List sub-view (read-only)."""
        return await self.client.getDiplomacyAllianceMembersView()


async def execute_send_ik_message(
    client: "Client",
    receiver_id: int,
    body: str,
    *,
    subject: str = "",
    msg_type: str = "50",
    reply_to: Optional[int] = None,
    current_island_id: Optional[int] = None,
    current_city_id: Optional[int] = None,
    action_name: str = "DiplomacyView.sendMessage",
) -> AjaxResponse:
    """Open ``view=sendIKMessage`` targeting ``receiver_id`` and submit ``#sendMessageBoxForm``."""
    from ikabot.ikariam._parsing import format_feedback, has_feedback_error
    from ikabot.ikariam.city import _collect_form_inputs

    text = f"{subject.strip()}\n{body}" if subject and subject.strip() else str(body)
    if str(msg_type) == "50" and not text.strip():
        raise ValueError("Message body cannot be empty")

    view_params: Dict[str, str] = {
        "view": "sendIKMessage",
        "receiverId": str(int(receiver_id)),
        "templateView": "sendIKMessage",
        "actionRequest": "REQUESTID",
        "ajax": "1",
    }
    if str(msg_type) != "50":
        view_params["msgType"] = str(msg_type)
    if reply_to is not None:
        view_params["replyTo"] = str(int(reply_to))
    if current_island_id is not None:
        view_params["backgroundView"] = "island"
        view_params["currentIslandId"] = str(int(current_island_id))
    else:
        view_params["backgroundView"] = "city"
        resolved_city_id = (
            current_city_id
            if current_city_id is not None
            else (
                client.selectedDropDownCity.id
                if getattr(client, "selectedDropDownCity", None) is not None
                else None
            )
        )
        if resolved_city_id is not None:
            view_params["currentCityId"] = str(int(resolved_city_id))

    view_resp = await client.post_ajax(params=view_params)
    if has_feedback_error(view_resp.feedback) or not view_resp.view_html:
        detail = format_feedback(view_resp.feedback) or "missing sendIKMessage view"
        raise ValueError(f"Could not open sendIKMessage for receiver {receiver_id}: {detail}")

    soup = make_soup(view_resp.view_html)
    form = soup.select_one("#sendMessageBoxForm") or soup.find("form")
    if form is None:
        raise ValueError(f"Could not find #sendMessageBoxForm for receiver {receiver_id}")

    payload = _collect_form_inputs(form)
    msg_select = form.select_one("select[name='msgType']")
    if msg_select is not None:
        available_types = {
            str(opt.get("value"))
            for opt in msg_select.find_all("option")
            if opt.get("value") is not None
        }
        if available_types and str(msg_type) not in available_types:
            raise ValueError(
                f"msgType={msg_type!r} is not available for receiver {receiver_id} "
                f"(available: {sorted(available_types)})"
            )
    payload["msgType"] = str(msg_type)
    payload["content"] = text

    submit_params: Dict[str, str] = {
        "backgroundView": view_params["backgroundView"],
        "templateView": "sendIKMessage",
        "actionRequest": "REQUESTID",
        "ajax": "1",
    }
    if "currentIslandId" in view_params:
        submit_params["currentIslandId"] = view_params["currentIslandId"]
    if "currentCityId" in view_params:
        submit_params["currentCityId"] = view_params["currentCityId"]

    return await client.post_action(
        payloadPost=payload,
        params=submit_params,
        metadata={
            "ambrosia_cost": 0,
            "receiverId": int(receiver_id),
            "msgType": str(msg_type),
        },
        action_name=action_name,
    )


class DiplomacyView:
    """Diplomacy Advisor mailbox view and tab navigator."""

    client: "Client"
    mailboxType: str
    messagesTabCount: int
    agoraTabCount: int
    allianceTabCount: int
    inboxCount: Optional[int]
    outboxCount: Optional[int]
    archiveInboxCount: Optional[int]
    archiveOutboxCount: Optional[int]
    currentMessageRange: Tuple[int, int]
    messages: List[DiplomacyMessage]

    _BOX_TO_VIEW = {
        "inbox": "diplomacyAdvisor",
        "outbox": "diplomacyAdvisorOutBox",
        "archiveInbox": "diplomacyAdvisorArchive",
        "archiveOutbox": "diplomacyAdvisorArchiveOutBox",
    }

    def __init__(
        self,
        client: "Client",
        viewData: Union[str, AjaxResponse],
        mailboxType: Optional[str] = None,
    ) -> None:
        """Parse Diplomacy mailbox entries, folder counts, tabs, and reply/offer links."""
        self.client = client
        resp, soup = parse_view_payload(viewData)
        self._diplomacy_response = resp

        if mailboxType is not None:
            self.mailboxType = mailboxType
        else:
            reverse_map = {v: k for k, v in self._BOX_TO_VIEW.items()}
            self.mailboxType = reverse_map.get(resp.view_name or "", "inbox")

        tab_counts = _parse_tab_counts(soup)
        self.messagesTabCount = tab_counts.get("js_tab_diplomacyAdvisor", 0)
        self.agoraTabCount = tab_counts.get("js_tab_diplomacyIslandBoard", 0)
        self.allianceTabCount = tab_counts.get("js_tab_diplomacyAlly", 0)

        self.inboxCount = None
        self.outboxCount = None
        self.archiveInboxCount = None
        self.archiveOutboxCount = None
        for a in soup.select("a[href*='diplomacyAdvisor']"):
            href = str(a.get("href") or "")
            m_cnt = _TAB_COUNT_RE.search(a.get_text(" ", strip=True))
            cnt = parse_int(m_cnt.group(1)) if m_cnt else None
            if cnt is None:
                continue
            view_param = parse_query_str(href, "view")
            if view_param == "diplomacyAdvisor":
                self.inboxCount = cnt
            elif view_param == "diplomacyAdvisorOutBox":
                self.outboxCount = cnt
            elif view_param == "diplomacyAdvisorArchive":
                self.archiveInboxCount = cnt
            elif view_param == "diplomacyAdvisorArchiveOutBox":
                self.archiveOutboxCount = cnt

        range_text = ""
        for td in soup.select("#deleteMessages td"):
            txt = td.get_text(" ", strip=True)
            if re.fullmatch(r"\d+\s*-\s*\d+", txt):
                range_text = txt
                break
        m_range = re.search(r"(\d+)\s*-\s*(\d+)", range_text)
        self.currentMessageRange = (
            (int(m_range.group(1)), int(m_range.group(2))) if m_range else (0, 0)
        )
        current_offset = max(0, self.currentMessageRange[0] - 1)
        self._prevLinkParams, self._nextLinkParams = _extract_paginator_links(
            soup, current_offset
        )

        self.messages = []
        td = resp.template_data
        for tr in soup.select("tr.entry[id^='message']"):
            raw_id = str(tr.get("id") or "")
            msg_id = parse_int(raw_id[len("message") :])
            if msg_id is None:
                continue

            cells = tr.find_all("td", recursive=False)
            cb = tr.select_one(f"input[name='deleteId[{msg_id}]']")
            tr_classes = set(tr.get("class") or [])
            is_new = (
                "new" in tr_classes
                or "unread" in tr_classes
                or (cb is not None and str(cb.get("value") or "") == "new")
            )

            partner_cell = cells[2] if len(cells) > 2 else None
            partner_name = (
                partner_cell.get_text(" ", strip=True) if partner_cell else ""
            )
            partner_flag = _extract_flag_tag(partner_cell)

            subj_cell = tr.select_one("td.subject") or (cells[3] if len(cells) > 3 else None)
            subject = subj_cell.get_text(" ", strip=True) if subj_cell else ""

            city_cell = cells[4] if len(cells) > 4 else None
            city_a = city_cell.find("a") if city_cell else None
            city_href = str(city_a["href"]) if city_a and city_a.get("href") else None
            city_name, city_coords = _extract_coords(
                city_a.get_text(" ", strip=True) if city_a else ""
            )
            city_id = parse_query_int(city_href, "selectCity") if city_href else None
            island_id = parse_query_int(city_href, "islandId") if city_href else None

            date_cell = cells[5] if len(cells) > 5 else None
            parsed_date = _parse_date(date_cell.get_text(" ", strip=True)) if date_cell else None

            mail_tr = soup.find(id=f"tbl_mail{msg_id}")
            mail_td = mail_tr.select_one("td") if mail_tr else mail_tr
            body_html = str(mail_td) if mail_td is not None else ""
            body_text = mail_td.get_text(" ", strip=True) if mail_td is not None else ""

            reply_tr = soup.find(id=f"tbl_reply{msg_id}")
            answer_a = (
                reply_tr.select_one("a[href*='sendIKMessage'][href*='replyTo=']")
                if reply_tr
                else None
            )
            if answer_a and "msgType=51" in str(answer_a.get("href") or ""):
                answer_a = next(
                    (
                        a
                        for a in reply_tr.select("a[href*='sendIKMessage']")
                        if "replyTo=" in str(a.get("href") or "")
                        and "msgType=51" not in str(a.get("href") or "")
                    ),
                    None,
                )
            reply_all_a = (
                reply_tr.select_one("a[href*='sendIKMessage'][href*='msgType=51']")
                if reply_tr
                else None
            )
            accept_a = (
                reply_tr.select_one("a.answerYes, a[href*='msgType=79']")
                if reply_tr
                else None
            )
            decline_a = (
                reply_tr.select_one("a.answerNo, a[href*='msgType=80']")
                if reply_tr
                else None
            )
            ignore_a = (
                reply_tr.select_one("a[href*='function=ignorePlayer']")
                if reply_tr
                else None
            )

            answer_href = (
                str(answer_a["href"]) if answer_a and answer_a.get("href") else None
            )
            accept_href = (
                str(accept_a["href"]) if accept_a and accept_a.get("href") else None
            )
            decline_href = (
                str(decline_a["href"]) if decline_a and decline_a.get("href") else None
            )
            reply_all_href = (
                str(reply_all_a["href"])
                if reply_all_a and reply_all_a.get("href")
                else None
            )
            ignore_href = (
                str(ignore_a["href"]) if ignore_a and ignore_a.get("href") else None
            )

            partner_id = (
                parse_query_int(answer_href or "", "receiverId")
                or parse_query_int(accept_href or "", "receiverId")
                or parse_query_int(ignore_href or "", "ignoreId")
            )

            offer_btn = td.get(f"js_offerButton_{msg_id}")
            archive_href = (
                str(offer_btn["href"])
                if isinstance(offer_btn, dict) and offer_btn.get("href")
                else None
            )

            self.messages.append(
                DiplomacyMessage(
                    messageId=msg_id,
                    isNew=is_new,
                    partnerId=partner_id,
                    partnerName=partner_name,
                    partnerFlagTag=partner_flag,
                    subject=subject,
                    isCircular=reply_all_href is not None,
                    isTreatyOffer=accept_href is not None or decline_href is not None,
                    cityName=city_name,
                    cityCoords=city_coords,
                    cityId=city_id,
                    islandId=island_id,
                    date=parsed_date,
                    bodyText=body_text,
                    bodyHtml=body_html,
                    answerHref=answer_href,
                    replyAllHref=reply_all_href,
                    acceptHref=accept_href,
                    declineHref=decline_href,
                    ignoreHref=ignore_href,
                    archiveHref=archive_href,
                )
            )

    def getMessage(self, messageId: int) -> Optional[DiplomacyMessage]:
        """Return the parsed message matching ``messageId``, or ``None``."""
        return next((m for m in self.messages if m.id == messageId), None)

    async def getInbox(self, offset: int = 0) -> "DiplomacyView":
        """Open the Diplomacy Inbox (read-only)."""
        return await self.client.getDiplomacyView(box="inbox", offset=offset)

    async def getOutbox(self, offset: int = 0) -> "DiplomacyView":
        """Open the Diplomacy Outbox (read-only)."""
        return await self.client.getDiplomacyView(box="outbox", offset=offset)

    async def getArchiveInbox(self, offset: int = 0) -> "DiplomacyView":
        """Open the Diplomacy Archived Inbox (read-only)."""
        return await self.client.getDiplomacyView(box="archiveInbox", offset=offset)

    async def getArchiveOutbox(self, offset: int = 0) -> "DiplomacyView":
        """Open the Diplomacy Archived Outbox (read-only)."""
        return await self.client.getDiplomacyView(box="archiveOutbox", offset=offset)

    async def getPreviousPage(self) -> "DiplomacyView":
        """Fetch the previous page of messages in the current mailbox."""
        if self._prevLinkParams is not None:
            resp = await self.client.get_ajax(params=self._prevLinkParams)
            if resp.view_html is None:
                raise ValueError("Missing view HTML in diplomacy advisor response")
            return DiplomacyView(self.client, resp, mailboxType=self.mailboxType)
        prev_offset = (
            max(0, (self.currentMessageRange[0] - 1) - 10)
            if self.currentMessageRange[0] > 1
            else 0
        )
        return await self.client.getDiplomacyView(box=self.mailboxType, offset=prev_offset)

    async def getNextPage(self) -> "DiplomacyView":
        """Fetch the next page of messages in the current mailbox."""
        if self._nextLinkParams is not None:
            resp = await self.client.get_ajax(params=self._nextLinkParams)
            if resp.view_html is None:
                raise ValueError("Missing view HTML in diplomacy advisor response")
            return DiplomacyView(self.client, resp, mailboxType=self.mailboxType)
        next_offset = self.currentMessageRange[1] if self.currentMessageRange[1] > 0 else 0
        return await self.client.getDiplomacyView(box=self.mailboxType, offset=next_offset)

    async def getAgora(self, islandId: Optional[int] = None) -> DiplomacyAgoraView:
        """Open the Diplomacy Agora tab (read-only)."""
        return await self.client.getDiplomacyAgoraView(islandId=islandId)

    async def getTreaties(self) -> DiplomacyTreatiesView:
        """Open the Diplomacy Treaties tab (read-only)."""
        return await self.client.getDiplomacyTreatiesView()

    async def getAlliance(self) -> DiplomacyAllianceView:
        """Open the Diplomacy Alliance tab (read-only)."""
        return await self.client.getDiplomacyAllianceView()

    async def getAllianceInfo(self) -> DiplomacyAllianceInfoView:
        """Open the Diplomacy Alliance Information sub-view (read-only)."""
        return await self.client.getDiplomacyAllianceInfoView()

    async def getAllianceMembers(self) -> DiplomacyAllianceMembersView:
        """Open the Diplomacy Alliance Member List sub-view (read-only)."""
        return await self.client.getDiplomacyAllianceMembersView()

    async def getIgnoredPlayers(self) -> List[Dict[str, Any]]:
        """Return ignored players listed on the Ignored Players tab (read-only)."""
        return await self.client.getIgnoredPlayers()

    async def sendMessage(
        self,
        receiverId: int,
        body: str,
        *,
        subject: str = "",
        msgType: str = "50",
        replyTo: Optional[int] = None,
    ) -> AjaxResponse:
        """Send a personal diplomatic message or treaty request to ``receiverId``."""
        return await execute_send_ik_message(
            self.client,
            int(receiverId),
            body,
            subject=subject,
            msg_type=msgType,
            reply_to=replyTo,
            action_name="DiplomacyView.sendMessage",
        )

    async def sendCircularMessage(
        self,
        body: str,
        *,
        allyId: Optional[int] = None,
        replyTo: Optional[int] = None,
    ) -> AjaxResponse:
        """Send an alliance circular message."""
        ...

    async def acceptTreatyOffer(self, messageId: int) -> AjaxResponse:
        """Accept an incoming cultural goods or diplomatic treaty offer."""
        ...

    async def declineTreatyOffer(self, messageId: int) -> AjaxResponse:
        """Decline an incoming cultural goods or diplomatic treaty offer."""
        ...

    async def markAsRead(self, messageIds: List[int]) -> AjaxResponse:
        """Mark the specified message IDs as read."""
        ...

    async def deleteMessages(self, messageIds: List[int]) -> AjaxResponse:
        """Delete the specified message IDs."""
        ...

    async def archiveMessage(self, messageId: int) -> AjaxResponse:
        """Archive the specified message ID using Ambrosia/inventory coins."""
        ...

    async def reportMessage(self, messageId: int) -> AjaxResponse:
        """Report the specified message to a game operator."""
        ...

    async def ignorePlayer(self, playerId: int) -> AjaxResponse:
        """Add a player to the ignored players list."""
        ...

    async def unignorePlayer(self, playerId: int) -> AjaxResponse:
        """Remove a player from the ignored players list."""
        ...

    async def searchPlayers(self, searchUser: str) -> List[Dict[str, Any]]:
        """Search players via ``diplomacyAdvisorSearchUser`` (read-only)."""
        resp = await self.client.get_ajax(
            params={
                "view": "diplomacyAdvisorSearchUser",
                "searchUser": searchUser,
            }
        )
        if not resp.view_html:
            return []
        soup = make_soup(resp.view_html)
        results: List[Dict[str, Any]] = []
        for tr in soup.select("table#userSearchTable tr"):
            if tr.select_one("th") or tr.select_one("td[colspan]"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 5:
                continue
            msg_a = tds[5].select_one("a[href*='receiverId']") if len(tds) >= 6 else None
            results.append(
                {
                    "position": parse_int(tds[0].get_text(" ", strip=True)),
                    "title": tds[1].get_text(" ", strip=True) or None,
                    "username": tds[2].get_text(" ", strip=True),
                    "alliance": tds[3].get_text(" ", strip=True) or None,
                    "points": parse_int(tds[4].get_text(" ", strip=True)) or 0,
                    "playerId": (
                        parse_query_int(str(msg_a["href"]), "receiverId")
                        if msg_a and msg_a.get("href")
                        else None
                    ),
                }
            )
        return results

    async def searchAlliances(
        self,
        *,
        name: str = "",
        tag: str = "",
    ) -> List[Dict[str, Any]]:
        """Search alliances via ``diplomacyAllySearch`` (read-only)."""
        params: Dict[str, str] = {"view": "diplomacyAllySearch"}
        if name:
            params["name"] = name
        if tag:
            params["tag"] = tag
        resp = await self.client.get_ajax(params=params)
        if not resp.view_html:
            return []
        soup = make_soup(resp.view_html)
        results: List[Dict[str, Any]] = []
        for tr in soup.select("table.embassyTable tr"):
            if tr.select_one("th") or tr.select_one("td[colspan]"):
                continue
            tds = tr.find_all("td", recursive=False)
            if len(tds) < 4:
                continue
            ally_a = tr.select_one("a[href*='allyId']")
            results.append(
                {
                    "tag": tds[0].get_text(" ", strip=True),
                    "name": tds[1].get_text(" ", strip=True),
                    "members": parse_int(tds[2].get_text(" ", strip=True)) or 0,
                    "pointsText": tds[3].get_text(" ", strip=True),
                    "allyId": (
                        parse_query_int(str(ally_a["href"]), "allyId")
                        if ally_a and ally_a.get("href")
                        else None
                    ),
                }
            )
        return results

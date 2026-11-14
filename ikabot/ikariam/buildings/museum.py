"""Museum building model (`view=museum`, `buildingId=10`)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import AjaxResponse, parse_int, parse_query_int
from ikabot.ikariam.buildings._base import Building, parse_view_payload

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import IkariamClient


_GOODS_RATIO_RE = re.compile(r"(\d+)\s*/\s*(\d+)")
_SLIDER_CITY_ID_RE = re.compile(r"(?:goodscity_|city_)(\d+)")
_INI_VALUE_RE = re.compile(r"iniValue\s*:\s*(\d+)")
_MAX_VALUE_RE = re.compile(r"maxValue\s*:\s*(\d+)")
_BASIC_SAT_RE = re.compile(r'basicSatisfaction\s*\[\s*["\'][^"\']+["\']\s*\]\s*=\s*(-?\d+)')
_WS_RE = re.compile(r"\s+")


def _clean_text(value: Any) -> str:
    """Collapse internal whitespace cleanly."""
    return _WS_RE.sub(" ", str(value or "")).strip()


def _parse_treaty_row_common(
    row: Tag,
) -> Optional[Tuple[Tag, Optional[int], str, Optional[str], Optional[str], str, Optional[str], Optional[str]]]:
    """Extract common fields from a Museum partner/request table row."""
    player_td = row.select_one("td.player")
    if player_td is None:
        return None

    avatar_span = player_td.select_one("span.avatarName")
    player_name = _clean_text(
        avatar_span.get_text(" ", strip=True)
        if avatar_span is not None
        else player_td.get_text(" ", strip=True)
    )
    if not player_name:
        return None

    country: Optional[str] = None
    flag_span = player_td.select_one("span.flag")
    if flag_span is not None:
        for cls in flag_span.get("class", []):
            if cls != "flag":
                country = cls
                break

    ally_td = row.select_one("td.ally")
    ally_text = _clean_text(ally_td.get_text(" ", strip=True)) if ally_td else ""
    alliance = None if ally_text in ("", "-") else ally_text

    capital_td = row.select_one("td.capital")
    capital = _clean_text(capital_td.get_text(" ", strip=True)) if capital_td else ""

    write_link = row.select_one("td.actions a.writeMsg[href]")
    cancel_link = row.select_one("td.actions a.cancelTreaty[href]")
    send_msg_url = write_link.get("href") if write_link else None
    cancel_url = cancel_link.get("href") if cancel_link else None

    player_id = parse_query_int(send_msg_url, "receiverId")
    if player_id is None:
        player_id = parse_query_int(cancel_url, "receiverId")

    return (
        player_td,
        player_id,
        player_name,
        country,
        alliance,
        capital,
        send_msg_url,
        cancel_url,
    )


@dataclass
class CulturalTreatyRequest:
    """Pending incoming cultural goods treaty request shown on ``view=museum``."""

    playerId: Optional[int]
    playerName: str
    alliance: Optional[str] = None
    capital: str = ""
    sendMessageUrl: Optional[str] = None
    rejectUrl: Optional[str] = None


@dataclass
class CulturalTreatyPartner:
    """Active cultural goods treaty partner from ``view=museumTreaties``."""

    playerId: Optional[int]
    playerName: str
    country: Optional[str] = None
    alliance: Optional[str] = None
    capital: str = ""
    isInactive: bool = False
    isVacation: bool = False
    sendMessageUrl: Optional[str] = None
    cancelUrl: Optional[str] = None


@dataclass
class MuseumCityAssignment:
    """Per-city cultural goods distribution from ``view=culturalPossessions_assign``."""

    cityId: Optional[int]
    cityName: str
    assignedGoods: int = 0
    maxGoods: int = 0
    satisfactionStatus: str = ""
    basicSatisfaction: Optional[int] = None


class Museum(Building):
    """Ikariam Museum building model (``view=museum``).

    Supports the primary city exhibition overview (``view=museum``), active
    treaty partners (``view=museumTreaties``), and the empire-wide cultural
    goods distribution tab (``view=culturalPossessions_assign``).
    """

    buildingId: int = 10
    buildingType: str = "museum"

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
        self.displayedGoods: int = 0
        self.maxGoods: int = 0
        self.satisfactionBonus: int = 0
        self.findTreatyPartnerUrl: Optional[str] = None
        self.treatyRequests: List[CulturalTreatyRequest] = []
        self.treaties: List[CulturalTreatyPartner] = []
        self.unassignedGoods: int = 0
        self.totalTreaties: int = 0
        self.cityAssignments: List[MuseumCityAssignment] = []

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse the Museum view (or dispatch if a secondary tab view was passed)."""
        find_btn = soup.select_one("#findTreatyPartner a.button[href]")
        self.findTreatyPartnerUrl = find_btn.get("href") if find_btn else None

        if soup.select_one("#tab_museum") is not None:
            self._parse_museum_tab(soup)
            return
        if soup.select_one("#tab_museumTreaties") is not None:
            self._parse_treaties_tab(soup)
            return
        if soup.select_one("#tab_culturalPossessions_assign") is not None:
            self._parse_assign_tab(soup)
            return

        self._parse_museum_tab(soup)

    def _parse_museum_tab(self, soup: BeautifulSoup) -> None:
        """Parse `#tab_museum`: displayed goods, bonus, and pending requests."""
        tab = soup.select_one("#tab_museum") or soup
        self.displayedGoods = 0
        self.maxGoods = 0
        self.satisfactionBonus = 0
        self.treatyRequests = []

        goods_div = tab.select_one(".culturalGoods .goods")
        if goods_div is not None:
            match = _GOODS_RATIO_RE.search(goods_div.get_text(" ", strip=True))
            if match:
                self.displayedGoods = int(match.group(1))
                self.maxGoods = int(match.group(2))

        bonus_span = tab.select_one(".culturalGoods .result span.bold")
        if bonus_span is not None:
            bonus = parse_int(bonus_span.get_text(" ", strip=True))
            if bonus is not None:
                self.satisfactionBonus = bonus

        for tr in tab.select("table.table01 tr"):
            parsed = _parse_treaty_row_common(tr)
            if parsed is None:
                continue
            _, player_id, player_name, _, alliance, capital, send_url, reject_url = parsed
            self.treatyRequests.append(
                CulturalTreatyRequest(
                    playerId=player_id,
                    playerName=player_name,
                    alliance=alliance,
                    capital=capital,
                    sendMessageUrl=send_url,
                    rejectUrl=reject_url,
                )
            )

    def _parse_treaties_tab(self, soup: BeautifulSoup) -> None:
        """Parse `#tab_museumTreaties`: active cultural goods treaty partners."""
        tab = soup.select_one("#tab_museumTreaties") or soup
        partners: List[CulturalTreatyPartner] = []

        for tr in tab.select("table.table01 tr"):
            parsed = _parse_treaty_row_common(tr)
            if parsed is None:
                continue
            player_td, player_id, player_name, country, alliance, capital, send_url, cancel_url = parsed

            td_classes = player_td.get("class", [])
            is_inactive = "gray" in td_classes or player_td.select_one(".inactive") is not None
            is_vacation = False
            if "vacation" in td_classes or player_td.select_one(".vacation") is not None:
                is_vacation = True
            else:
                for img in player_td.select("img"):
                    meta = " ".join(
                        [
                            str(img.get("title", "")),
                            str(img.get("alt", "")),
                            str(img.get("src", "")),
                        ]
                    ).lower()
                    if "vacation" in meta or "urlaub" in meta or "palm" in meta:
                        is_vacation = True
                        break
                    if not meta.strip():
                        # Ikariam renders an inline <img> next to avatarName for vacation mode.
                        is_vacation = True
                        break

            partners.append(
                CulturalTreatyPartner(
                    playerId=player_id,
                    playerName=player_name,
                    country=country,
                    alliance=alliance,
                    capital=capital,
                    isInactive=is_inactive,
                    isVacation=is_vacation,
                    sendMessageUrl=send_url,
                    cancelUrl=cancel_url,
                )
            )

        self.treaties = partners

    def _parse_assign_tab(self, soup: BeautifulSoup) -> None:
        """Parse `#tab_culturalPossessions_assign`: unassigned count and city sliders."""
        tab = soup.select_one("#tab_culturalPossessions_assign") or soup
        amount_el = tab.select_one("#cgAmount")
        avail_el = tab.select_one("#cgAvailable")

        unassigned = parse_int(amount_el.get_text(" ", strip=True)) if amount_el else None
        total = parse_int(avail_el.get_text(" ", strip=True)) if avail_el else None
        self.unassignedGoods = unassigned if unassigned is not None else 0
        self.totalTreaties = total if total is not None else 0

        assignments: List[MuseumCityAssignment] = []
        for li in tab.select("#moveCulturalGoods ul > li"):
            city_div = li.select_one(".city")
            city_name = _clean_text(city_div.get_text(" ", strip=True)) if city_div else ""

            city_input = li.select_one("input[name^='goodscity_']")
            city_id: Optional[int] = None
            for attr_src in (
                city_input.get("name", "") if city_input else "",
                city_input.get("id", "") if city_input else "",
            ):
                m = _SLIDER_CITY_ID_RE.search(attr_src)
                if m:
                    city_id = int(m.group(1))
                    break

            max_span = li.select_one(".changeAmount span")
            max_goods = parse_int(max_span.get_text(" ", strip=True)) if max_span else None

            sat_div = li.select_one(".satisfaction")
            sat_status = _clean_text(sat_div.get_text(" ", strip=True)) if sat_div else ""
            if not sat_status and sat_div is not None:
                for cls in sat_div.get("class", []):
                    if cls != "satisfaction":
                        sat_status = cls
                        break

            # The static HTML <input value="0"> is always 0 until YUI runs; real values live in <script>.
            assigned_goods: Optional[int] = None
            basic_sat: Optional[int] = None
            script_text = " ".join(s.get_text(" ") for s in li.select("script"))
            if script_text:
                if city_id is None:
                    m_cid = _SLIDER_CITY_ID_RE.search(script_text)
                    if m_cid:
                        city_id = int(m_cid.group(1))
                m_ini = _INI_VALUE_RE.search(script_text)
                if m_ini:
                    assigned_goods = int(m_ini.group(1))
                if max_goods is None:
                    m_max = _MAX_VALUE_RE.search(script_text)
                    if m_max:
                        max_goods = int(m_max.group(1))
                m_sat = _BASIC_SAT_RE.search(script_text)
                if m_sat:
                    basic_sat = int(m_sat.group(1))

            if assigned_goods is None and city_input is not None:
                assigned_goods = parse_int(city_input.get("value"))

            assignments.append(
                MuseumCityAssignment(
                    cityId=city_id,
                    cityName=city_name,
                    assignedGoods=assigned_goods if assigned_goods is not None else 0,
                    maxGoods=max_goods if max_goods is not None else 0,
                    satisfactionStatus=sat_status,
                    basicSatisfaction=basic_sat,
                )
            )

        self.cityAssignments = assignments

    def parseTreaties(self, viewData: Union[str, AjaxResponse]) -> "Museum":
        """Parse ``view=museumTreaties`` response offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self._parse_treaties_tab(soup)
        return self

    def parseAssign(self, viewData: Union[str, AjaxResponse]) -> "Museum":
        """Parse ``view=culturalPossessions_assign`` response offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self._parse_assign_tab(soup)
        return self

    async def loadTreaties(self) -> "Museum":
        """Fetch and parse ``view=museumTreaties``."""
        resp = await self._fetch_view(
            view="museumTreaties",
            activeTab="tab_museumTreaties",
        )
        return self.parseTreaties(resp)

    async def loadAssign(self) -> "Museum":
        """Fetch and parse ``view=culturalPossessions_assign``."""
        resp = await self._fetch_view(
            view="culturalPossessions_assign",
            activeTab="tab_culturalPossessions_assign",
        )
        return self.parseAssign(resp)

    async def loadAllTabs(self) -> "Museum":
        """Refresh the primary Museum view and both secondary tabs."""
        await self.load()
        await self.loadTreaties()
        await self.loadAssign()
        return self

    # --- Action Methods & Stubs ---

    async def assignCulturalGood(self, cityId: int, amount: int) -> "Museum":
        """Assign ``amount`` cultural goods to ``cityId`` while preserving other cities."""
        return await self.assignCulturalGoods({int(cityId): int(amount)})

    async def assignCulturalGoods(self, distribution: Dict[int, int]) -> "Museum":
        """Redistribute cultural goods across multiple cities and reload assign state."""
        if not self.cityAssignments:
            await self.loadAssign()

        known_ids = {
            entry.cityId
            for entry in self.cityAssignments
            if entry.cityId is not None
        }
        unknown = [cid for cid in distribution if int(cid) not in known_ids]
        if unknown:
            raise ValueError(f"Unknown cityId(s) in cultural goods distribution: {unknown}")

        payload: Dict[str, str] = {}
        for entry in self.cityAssignments:
            if entry.cityId is None:
                continue
            target = int(distribution.get(entry.cityId, entry.assignedGoods))
            if target < 0:
                raise ValueError(f"Cultural goods count for city {entry.cityId} cannot be negative ({target})")
            payload[f"goodscity_{entry.cityId}"] = str(target)

        resp = await self._post_building_action(
            action="culturalPossessions",
            function="assign",
            templateView="culturalPossessions_assign",
            extraParams={"activeTab": "tab_culturalPossessions_assign"},
            payloadPost=payload,
            action_name="Museum.assignCulturalGoods",
            refresh=False,
        )
        if resp.view_html and "moveCulturalGoodsForm" in resp.view_html:
            self.parseAssign(resp)
        else:
            await self.loadAssign()
        return self

    async def sendCulturalTreatyRequest(
        self,
        receiverId: int,
        message: str = "",
    ) -> AjaxResponse:
        """Send a cultural goods treaty proposal (``msgType='77'``) to ``receiverId``."""
        from ikabot.ikariam.advisors import execute_send_ik_message

        client = self._require_client()
        resp = await execute_send_ik_message(
            client,
            int(receiverId),
            message or "Would you like to conclude a Cultural Goods Treaty?",
            msg_type="77",
            current_city_id=self.cityId,
            action_name="Museum.sendCulturalTreatyRequest",
        )
        await self.load()
        return resp

    async def cancelCulturalTreaty(self, partnerId: int) -> Any:
        """Cancel an existing cultural goods treaty (read-only stub)."""
        ...

    async def rejectCulturalTreatyRequest(self, playerId: int) -> Any:
        """Reject an incoming cultural goods treaty request (read-only stub)."""
        ...

    async def findTreatyPartner(self) -> Any:
        """Open/trigger Ambrosia treaty partner search (read-only stub)."""
        ...

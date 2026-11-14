"""Embassy building model (`view=embassy`, `buildingId=12`)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import AjaxResponse, parse_int, parse_query_int
from ikabot.ikariam.buildings._base import (
    Building,
    parse_labeled_coords,
    parse_view_payload,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import IkariamClient


_DIPLOMACY_POINTS_RE = re.compile(r"Diplomacy\s+Points\s*:\s*(\d+)", re.IGNORECASE)
_PLACEMENT_RE = re.compile(r"(\d+)\s*\(([\d,.\s]+)\)")
_SCALED_NUM_RE = re.compile(r"^\s*([\d,.]+)\s*([KMBG]?)\s*$", re.IGNORECASE)
_SWITCH_TAB_RE = re.compile(r'switchTab\(["\']([^"\']+)["\']\)')
_WS_RE = re.compile(r"\s+")

_MULTIPLIERS = {
    "": 1,
    "K": 1_000,
    "M": 1_000_000,
    "B": 1_000_000_000,
    "G": 1_000_000_000,
}


def _clean_text(value: Any) -> str:
    """Collapse internal whitespace cleanly."""
    return _WS_RE.sub(" ", str(value or "")).strip()


def _parse_scaled_points(text: str) -> Optional[int]:
    """Parse Ikariam abbreviated or comma-formatted point strings (e.g. ``940.80M``)."""
    cleaned = _clean_text(text)
    if not cleaned:
        return None
    match = _SCALED_NUM_RE.match(cleaned)
    if match:
        num_str, suffix = match.group(1), match.group(2).upper()
        mult = _MULTIPLIERS.get(suffix)
        if suffix and mult:
            try:
                return int(round(float(num_str.replace(",", "")) * mult))
            except ValueError:
                return None
    return parse_int(cleaned)


def _extract_flag_and_name(container: Optional[Tag], name_selector: str) -> Tuple[Optional[str], str]:
    """Extract ``(countryCode, displayName)`` from a ``span.flag`` container."""
    if container is None:
        return None, ""
    country: Optional[str] = None
    flag_span = container.select_one("span.flag")
    if flag_span is not None:
        for cls in flag_span.get("class", []):
            if cls != "flag":
                country = cls
                break
    name_el = container.select_one(name_selector)
    name = _clean_text(
        name_el.get_text(" ", strip=True)
        if name_el is not None
        else container.get_text(" ", strip=True)
    )
    return country, name


@dataclass
class AllianceInfo:
    """Alliance summary shown on the primary ``tabEmbassy`` view."""

    allyId: Optional[int] = None
    tag: str = ""
    name: str = ""
    foundingDate: str = ""
    memberCount: int = 0
    shortDescription: str = ""
    placementRank: Optional[int] = None
    placementPoints: Optional[int] = None
    homepage: Optional[str] = None
    freeDiplomacyPoints: Optional[int] = None
    playerRank: str = ""


@dataclass
class EmbassyMemberCity:
    """City entry listed under an alliance member's expandable city tooltip."""

    cityId: Optional[int]
    islandId: Optional[int]
    cityName: str
    coords: Tuple[int, int] = (0, 0)


@dataclass
class EmbassyMember:
    """Single alliance member row parsed from ``activeTab=tabEmbassyMembers``."""

    avatarId: Optional[int]
    name: str
    country: Optional[str] = None
    status: str = ""
    lastActionDate: Optional[str] = None
    rank: str = ""
    points: Optional[int] = None
    cityCount: int = 0
    cities: List[EmbassyMemberCity] = field(default_factory=list)
    sendMessageUrl: Optional[str] = None


@dataclass
class AllianceSearchEntry:
    """Alliance search result row from ``activeTab=tabEmbassySearchAlly``."""

    allyId: Optional[int]
    tag: str
    name: str
    country: Optional[str] = None
    members: int = 0
    pointsText: str = ""
    points: Optional[int] = None
    allyPageUrl: Optional[str] = None


class Embassy(Building):
    """Ikariam Embassy building model (``view=embassy``).

    Supports the alliance overview (``tabEmbassy``), member roster
    (``tabEmbassyMembers``), internal alliance page (``tabEmbassyAllyPage``),
    and alliance search (``tabEmbassySearchAlly``).
    """

    buildingId: int = 12
    buildingType: str = "embassy"

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
        self.activeTab: str = "tabEmbassy"
        self.diplomacyPoints: Optional[int] = None
        self.allyId: Optional[int] = None
        self.inAlliance: bool = False
        self.alliance: Optional[AllianceInfo] = None
        self.canSendCircularMessage: bool = False
        self.canViewTreaties: bool = False
        self.canQuitAlliance: bool = False
        self.circularMessageUrl: Optional[str] = None
        self.treatiesUrl: Optional[str] = None
        self.quitUrl: Optional[str] = None
        self.members: List[EmbassyMember] = []
        self.internalAlliancePageHtml: str = ""
        self.internalAlliancePageText: str = ""
        self.searchResults: List[AllianceSearchEntry] = []

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse Embassy header/sidebar metadata and the active tab body."""
        self._parse_common(soup)

        detected_tab: Optional[str] = None
        for script in soup.select("#mainview script"):
            m = _SWITCH_TAB_RE.search(script.get_text(" "))
            if m:
                detected_tab = m.group(1)
                break
        if detected_tab:
            self.activeTab = detected_tab

        if soup.select_one("#allyMemberList") is not None or self.activeTab == "tabEmbassyMembers":
            self._parse_members_dom(soup)
        elif soup.select_one("#mainview .content.allypage") is not None or self.activeTab == "tabEmbassyAllyPage":
            self._parse_ally_page_dom(soup)
        elif soup.select_one("#js_searchAllyForm") is not None or soup.select_one("table.embassyTable") is not None or self.activeTab == "tabEmbassySearchAlly":
            self._parse_search_ally_dom(soup)
        else:
            self.activeTab = "tabEmbassy"
            self._parse_overview_dom(soup)

    def _parse_common(self, soup: BeautifulSoup) -> None:
        """Parse diplomacy points and `#embassyMenu` sidebar actions."""
        mainview = soup.select_one("#mainview") or soup
        for p in mainview.select("p"):
            text = _clean_text(p.get_text(" ", strip=True))
            m = _DIPLOMACY_POINTS_RE.search(text)
            if m:
                self.diplomacyPoints = int(m.group(1))
                break

        menu = soup.select_one("#embassyMenu")
        if menu is not None:
            self.canSendCircularMessage = False
            self.canViewTreaties = False
            self.canQuitAlliance = False
            self.circularMessageUrl = None
            self.treatiesUrl = None
            self.quitUrl = None

            for link in menu.select("ul.sideNavigation a[href]"):
                href = link.get("href", "")
                if "msgType=51" in href or "sendIKMessage" in href:
                    self.canSendCircularMessage = True
                    self.circularMessageUrl = href
                    aid = parse_query_int(href, "allyId")
                    if aid is not None:
                        self.allyId = aid
                elif "embassyTreaties" in href:
                    self.canViewTreaties = True
                    self.treatiesUrl = href
                elif "embassyLeaveAlly" in href:
                    self.canQuitAlliance = True
                    self.quitUrl = href

    def _parse_overview_dom(self, soup: BeautifulSoup) -> None:
        """Parse the Alliance details table on ``tabEmbassy``."""
        table = soup.select_one("#mainview .contentBox01h table.table01")
        if table is None:
            self.inAlliance = False
            self.alliance = None
            return

        rows = table.select("tr")
        if not rows:
            self.inAlliance = False
            self.alliance = None
            return

        info = AllianceInfo(allyId=self.allyId)
        for idx, tr in enumerate(rows):
            cells = tr.select("td")
            if len(cells) < 2:
                continue
            label_raw = _clean_text(cells[0].get_text(" ", strip=True))
            value_raw = _clean_text(cells[1].get_text(" ", strip=True))
            label_lower = label_raw.rstrip(":").strip().lower()

            if idx == 0 or (label_raw.startswith("[") and label_raw.endswith("]:")):
                info.tag = label_raw.strip()[1:-2] if label_raw.startswith("[") and label_raw.endswith("]:") else label_raw.strip("[]: ")
                info.name = value_raw
                continue

            if "founding date" in label_lower:
                info.foundingDate = value_raw
            elif label_lower == "members":
                m_cnt = parse_int(value_raw)
                if m_cnt is not None:
                    info.memberCount = m_cnt
            elif "short description" in label_lower:
                info.shortDescription = value_raw
            elif "placement" in label_lower:
                m_place = _PLACEMENT_RE.search(value_raw)
                if m_place:
                    info.placementRank = parse_int(m_place.group(1))
                    info.placementPoints = parse_int(m_place.group(2))
                else:
                    info.placementRank = parse_int(cells[1].get("title") or value_raw)
            elif "homepage" in label_lower:
                info.homepage = None if value_raw in ("", "-") else value_raw
            elif "diplomacy points" in label_lower:
                info.freeDiplomacyPoints = parse_int(value_raw)
            elif "your rank" in label_lower:
                info.playerRank = value_raw

        self.inAlliance = True
        self.alliance = info

    def _parse_members_dom(self, soup: BeautifulSoup) -> None:
        """Parse `#allyMemberList` rows on ``tabEmbassyMembers``."""
        table = soup.select_one("#allyMemberList")
        members: List[EmbassyMember] = []
        if table is not None:
            for tr in table.select("tr"):
                if tr.find("th") is not None and tr.find("td") is None:
                    continue
                tds = tr.select("td")
                if len(tds) < 6:
                    continue

                status_td = tds[0]
                status = ""
                for cls in status_td.get("class", []):
                    if cls != "user_status":
                        status = cls
                        break
                last_action_raw = _clean_text(status_td.get_text(" ", strip=True))
                last_action = last_action_raw or None

                name_td = tds[1]
                profile_link = name_td.select_one("a[href]")
                avatar_id = parse_query_int(profile_link.get("href") if profile_link else None, "avatarId")
                country, player_name = _extract_flag_and_name(name_td, "span.avatarName")

                cities_td = tds[2]
                magnify = cities_td.select_one(".magnify_icon")
                city_count = parse_int(magnify.get_text(" ", strip=True)) if magnify else None
                cities: List[EmbassyMemberCity] = []
                for city_a in cities_td.select(".infoTip a.city[href], a.city[href]"):
                    href = city_a.get("href", "")
                    city_text = _clean_text(city_a.get_text(" ", strip=True))
                    cname, cx, cy = parse_labeled_coords(city_text)
                    cities.append(
                        EmbassyMemberCity(
                            cityId=parse_query_int(href, "selectCity"),
                            islandId=parse_query_int(href, "islandId"),
                            cityName=cname,
                            coords=(cx, cy),
                        )
                    )
                if city_count is None:
                    city_count = len(cities)

                rank = _clean_text(tds[3].get_text(" ", strip=True))
                points = parse_int(tds[4].get_text(" ", strip=True))

                msg_link = tds[5].select_one("a.message[href], a[href*='sendIKMessage']")
                send_msg_url = msg_link.get("href") if msg_link else None
                if avatar_id is None and send_msg_url:
                    avatar_id = parse_query_int(send_msg_url, "receiverId")

                members.append(
                    EmbassyMember(
                        avatarId=avatar_id,
                        name=player_name,
                        country=country,
                        status=status,
                        lastActionDate=last_action,
                        rank=rank,
                        points=points,
                        cityCount=city_count,
                        cities=cities,
                        sendMessageUrl=send_msg_url,
                    )
                )

        self.members = members

    def _parse_ally_page_dom(self, soup: BeautifulSoup) -> None:
        """Parse `.content.allypage` on ``tabEmbassyAllyPage``."""
        ally_div = soup.select_one("#mainview .content.allypage") or soup.select_one(".content.allypage")
        if ally_div is None:
            self.internalAlliancePageHtml = ""
            self.internalAlliancePageText = ""
            return
        self.internalAlliancePageHtml = ally_div.decode_contents().strip()
        self.internalAlliancePageText = _clean_text(ally_div.get_text(" ", strip=True))

    def _parse_search_ally_dom(self, soup: BeautifulSoup) -> None:
        """Parse `table.embassyTable` rows on ``tabEmbassySearchAlly``."""
        table = soup.select_one("table.embassyTable")
        results: List[AllianceSearchEntry] = []
        if table is not None:
            for tr in table.select("tr"):
                if tr.find("th") is not None and tr.find("td") is None:
                    continue
                tag_td = tr.select_one("td.tag")
                name_td = tr.select_one("td.name")
                members_td = tr.select_one("td.members")
                score_td = tr.select_one("td.score")
                action_link = tr.select_one("td.action a[href]")
                if tag_td is None or name_td is None:
                    continue

                tag_link = tag_td.select_one("a[href]")
                name_link = name_td.select_one("a[href]")
                ally_page_url = (
                    (action_link.get("href") if action_link else None)
                    or (name_link.get("href") if name_link else None)
                    or (tag_link.get("href") if tag_link else None)
                )
                ally_id = parse_query_int(ally_page_url, "allyId")
                tag = _clean_text(tag_td.get_text(" ", strip=True))
                country, name = _extract_flag_and_name(name_td, "span.allyName")
                members_cnt = parse_int(members_td.get_text(" ", strip=True)) if members_td else 0
                points_text = _clean_text(score_td.get_text(" ", strip=True)) if score_td else ""

                results.append(
                    AllianceSearchEntry(
                        allyId=ally_id,
                        tag=tag,
                        name=name,
                        country=country,
                        members=members_cnt if members_cnt is not None else 0,
                        pointsText=points_text,
                        points=_parse_scaled_points(points_text),
                        allyPageUrl=ally_page_url,
                    )
                )

        self.searchResults = results

    def parseMembers(self, viewData: Union[str, AjaxResponse]) -> "Embassy":
        """Parse ``activeTab=tabEmbassyMembers`` offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabEmbassyMembers"
        self._parse_common(soup)
        self._parse_members_dom(soup)
        return self

    def parseAllyPage(self, viewData: Union[str, AjaxResponse]) -> "Embassy":
        """Parse ``activeTab=tabEmbassyAllyPage`` offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabEmbassyAllyPage"
        self._parse_common(soup)
        self._parse_ally_page_dom(soup)
        return self

    def parseSearchAlly(self, viewData: Union[str, AjaxResponse]) -> "Embassy":
        """Parse ``activeTab=tabEmbassySearchAlly`` offline or after a fetch."""
        resp, soup = parse_view_payload(viewData)
        self._last_response = resp
        self.activeTab = "tabEmbassySearchAlly"
        self._parse_common(soup)
        self._parse_search_ally_dom(soup)
        return self

    async def loadMembers(self) -> "Embassy":
        """Fetch and parse ``activeTab=tabEmbassyMembers``."""
        resp = await self._fetch_view(view="embassy", activeTab="tabEmbassyMembers")
        return self.parseMembers(resp)

    async def loadAllyPage(self) -> "Embassy":
        """Fetch and parse ``activeTab=tabEmbassyAllyPage``."""
        resp = await self._fetch_view(view="embassy", activeTab="tabEmbassyAllyPage")
        return self.parseAllyPage(resp)

    async def loadSearchAlly(self) -> "Embassy":
        """Fetch and parse ``activeTab=tabEmbassySearchAlly``."""
        resp = await self._fetch_view(view="embassy", activeTab="tabEmbassySearchAlly")
        return self.parseSearchAlly(resp)

    async def loadAllTabs(self) -> "Embassy":
        """Refresh the primary Embassy overview and all three secondary tabs."""
        await self.load()
        await self.loadMembers()
        await self.loadAllyPage()
        await self.loadSearchAlly()
        return self

    # --- Action Stubs (Read-only model: intentionally unimplemented) ---

    async def sendAllianceMessage(self, subject: str, body: str) -> Any:
        """Send an alliance circular message (read-only stub)."""
        ...

    async def leaveAlliance(self) -> Any:
        """Leave the current alliance (read-only stub)."""
        ...

    async def inviteMember(self, playerId: int) -> Any:
        """Invite a player into the alliance (read-only stub)."""
        ...

    async def kickMember(self, avatarId: int, message: str = "") -> Any:
        """Dismiss a member from the alliance (read-only stub)."""
        ...

    async def searchAlliances(
        self,
        *,
        name: str = "",
        tag: str = "",
        minPoints: Optional[int] = None,
        maxPoints: Optional[int] = None,
        minMembers: Optional[int] = None,
        maxMembers: Optional[int] = None,
        minAvPoints: Optional[int] = None,
        maxAvPoints: Optional[int] = None,
    ) -> List[AllianceSearchEntry]:
        """Submit an alliance search query on ``tabEmbassySearchAlly`` and return results."""
        client = self._require_client()
        if self.position is None:
            raise ValueError("Embassy position is required to search alliances")

        payload = {
            "view": "embassy",
            "activeTab": "tabEmbassySearchAlly",
            "cityId": str(self.cityId),
            "position": str(self.position),
            "name": name,
            "tag": tag,
            "minPoints": "" if minPoints is None else str(minPoints),
            "maxPoints": "" if maxPoints is None else str(maxPoints),
            "minAvPoints": "" if minAvPoints is None else str(minAvPoints),
            "maxAvPoints": "" if maxAvPoints is None else str(maxAvPoints),
            "minMember": "" if minMembers is None else str(minMembers),
            "maxMember": "" if maxMembers is None else str(maxMembers),
        }
        resp = await client.post_ajax(
            payloadPost=payload,
            params={
                "view": "embassy",
                "activeTab": "tabEmbassySearchAlly",
                "cityId": str(self.cityId),
                "position": str(self.position),
                "backgroundView": "city",
                "currentCityId": str(self.cityId),
                "templateView": "embassy",
                "actionRequest": "REQUESTID",
            },
        )
        self.parseSearchAlly(resp)
        return self.searchResults

    async def applyToAlliance(self, allyId: int, message: str = "") -> Any:
        """Submit an alliance membership application (read-only stub)."""
        ...

    async def createAlliance(self, name: str, tag: str) -> Any:
        """Found a new alliance (read-only stub)."""
        ...

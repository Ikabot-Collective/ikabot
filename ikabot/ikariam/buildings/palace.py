"""Palace building model (``view=palace``)."""

from dataclasses import dataclass
import re
from typing import Any, List, Optional

from bs4 import BeautifulSoup, Tag

from ikabot.ikariam._parsing import AjaxResponse, parse_int
from ikabot.ikariam.buildings._base import parse_labeled_coords
from ikabot.ikariam.buildings._mixins import _GovernanceBuilding


@dataclass
class OccupiedLocationEntry:
    """Entry from the Occupied Cities or Occupied Ports table in the Palace."""

    name: str
    isCapital: bool
    townHallLevel: int
    islandName: str
    x: int
    y: int
    luxuryResource: Optional[str]
    actionUrl: Optional[str]


def _parse_occupied_box(
    box: Tag,
) -> tuple[Optional[int], Optional[int], List[OccupiedLocationEntry]]:
    """Extract occupied count, max slots, and rows from an Occupied Cities/Ports box."""
    h3 = box.find("h3")
    max_slots: Optional[int] = None
    cur_slots: Optional[int] = None
    if h3 is not None:
        m = re.search(r"\(\s*(\d+)\s*/\s*(\d+)\s*\)", h3.get_text(" ", strip=True))
        if m:
            cur_slots = int(m.group(1))
            max_slots = int(m.group(2))

    entries: List[OccupiedLocationEntry] = []
    tbl = box.select_one("table.table01")
    if tbl is not None:
        for tr in tbl.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 6:
                continue
            is_cap = tds[0].find("img") is not None
            name = tds[1].get_text(" ", strip=True)
            lvl = parse_int(tds[2].get_text(strip=True)) or 0
            island_name, x, y = parse_labeled_coords(tds[3].get_text(" ", strip=True))
            res_img = tds[4].find("img")
            lux = (
                str(res_img.get("title") or res_img.get("alt") or "").strip()
                if res_img is not None
                else None
            )
            act_a = tds[5].find("a")
            act_url = str(act_a["href"]) if act_a and act_a.get("href") else None
            entries.append(
                OccupiedLocationEntry(
                    name=name,
                    isCapital=is_cap,
                    townHallLevel=lvl,
                    islandName=island_name,
                    x=x,
                    y=y,
                    luxuryResource=lux or None,
                    actionUrl=act_url,
                )
            )
    return cur_slots, max_slots, entries


class Palace(_GovernanceBuilding):
    """Capital city Palace showing form of government, empire towns, and occupations."""

    buildingId = 11
    buildingType = "palace"

    governmentName: Optional[str]
    governmentDescription: Optional[str]
    governmentAdvantages: List[str]
    governmentDisadvantages: List[str]
    changeGovernmentUrl: Optional[str]
    occupiedCitiesCount: int
    maxOccupiedCities: Optional[int]
    occupiedCities: List[OccupiedLocationEntry]
    occupiedPortsCount: int
    maxOccupiedPorts: Optional[int]
    occupiedPorts: List[OccupiedLocationEntry]

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        self._parse_empire_table(soup)
        self.governmentName = None
        self.governmentDescription = None
        self.governmentAdvantages = []
        self.governmentDisadvantages = []
        self.changeGovernmentUrl = None
        self.occupiedCitiesCount = 0
        self.maxOccupiedCities = None
        self.occupiedCities = []
        self.occupiedPortsCount = 0
        self.maxOccupiedPorts = None
        self.occupiedPorts = []

        gov = soup.find(id="formOfRuleContent")
        if gov is not None:
            hl = gov.select_one(".government_desc .headline")
            if hl is not None:
                self.governmentName = hl.get_text(" ", strip=True)
            desc_p = gov.select_one(".government_desc p")
            if desc_p is not None:
                self.governmentDescription = desc_p.get_text(" ", strip=True)
            rev_a = gov.select_one(".revolution_button a")
            if rev_a is not None and rev_a.get("href"):
                self.changeGovernmentUrl = str(rev_a["href"])
            self.governmentAdvantages = [
                li.get_text(" ", strip=True)
                for li in gov.select(".government_advantages li")
            ]
            self.governmentDisadvantages = [
                li.get_text(" ", strip=True)
                for li in gov.select(".government_disadvantages li")
            ]

        for box in soup.select(".contentBox01h"):
            h3 = box.find("h3")
            if h3 is None:
                continue
            title = h3.get_text(" ", strip=True).lower()
            if title.startswith("occupied cities"):
                cnt, mx, rows = _parse_occupied_box(box)
                self.occupiedCitiesCount = cnt if cnt is not None else len(rows)
                self.maxOccupiedCities = mx
                self.occupiedCities = rows
            elif title.startswith("occupied ports"):
                cnt, mx, rows = _parse_occupied_box(box)
                self.occupiedPortsCount = cnt if cnt is not None else len(rows)
                self.maxOccupiedPorts = mx
                self.occupiedPorts = rows

    async def changeGovernment(self, governmentId: int) -> Any:
        """Initiate a revolution to switch the empire's form of government."""
        ...

    async def releaseOccupiedCity(self, targetCityId: int) -> Any:
        """Give up occupation of an occupied city."""
        ...

    async def releaseOccupiedPort(self, targetCityId: int) -> Any:
        """Give up occupation of an occupied port."""
        ...

"""Model for the Ikariam Dockyard building (``view=dockyard``)."""

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    parse_int,
)
from ikabot.ikariam.buildings._base import (
    Building,
    parse_labeled_coords,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


@dataclass
class DockyardCityEntry:
    """Single city row from the Dockyard empire overview table."""

    cityId: int
    cityName: str
    x: int
    y: int
    dockyardLevel: int
    portPosition: Optional[int] = None
    statusText: str = ""
    canBuyHere: bool = False
    buyUrl: Optional[str] = None


class Dockyard(Building):
    """Dockyard view model with freighter counts, limits, and per-city dockyard levels."""

    canBuyFreighters: bool
    purchasedFreighters: int
    availableFreighters: int
    freightersRemainingToBuy: int
    maxNormalFreighters: int
    phoenicianFreightersBought: int
    phoenicianFreightersMax: int
    totalDockyardLevels: int
    cities: List[DockyardCityEntry]

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a Dockyard building model without making HTTP requests."""
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        if not self.buildingType:
            self.buildingType = "dockyard"
        self._reset_fields()

    def _reset_fields(self) -> None:
        """Reset view-specific attributes before parsing a Dockyard payload."""
        self.canBuyFreighters = False
        self.purchasedFreighters = 0
        self.availableFreighters = 0
        self.freightersRemainingToBuy = 0
        self.maxNormalFreighters = 0
        self.phoenicianFreightersBought = 0
        self.phoenicianFreightersMax = 0
        self.totalDockyardLevels = 0
        self.cities = []

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Extract freighter purchase totals and per-city dockyard levels."""
        self._reset_fields()

        td = resp.template_data
        if "canBuyFreighters" in td:
            self.canBuyFreighters = bool(td.get("canBuyFreighters"))
        if "boughtNormalFreighters" in td:
            self.purchasedFreighters = parse_int(td.get("boughtNormalFreighters")) or 0
        if "freightersStillToBeBought" in td:
            self.freightersRemainingToBuy = (
                parse_int(td.get("freightersStillToBeBought")) or 0
            )
        if "phoenicianFreightersBought" in td:
            self.phoenicianFreightersBought = (
                parse_int(td.get("phoenicianFreightersBought")) or 0
            )
        if "phoenicianFreightersMax" in td:
            self.phoenicianFreightersMax = (
                parse_int(td.get("phoenicianFreightersMax")) or 0
            )

        summary_tbl = soup.select_one("#mainview table.gainAmbrosiaTable")
        if summary_tbl is not None:
            for tr in summary_tbl.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 2:
                    continue
                label = cells[0].get_text(" ", strip=True).lower()
                val_text = cells[1].get_text(" ", strip=True)
                if "purchased freighters" in label and "boughtNormalFreighters" not in td:
                    self.purchasedFreighters = parse_int(val_text) or 0
                elif "available freighters" in label:
                    self.availableFreighters = parse_int(val_text) or 0
                elif "phoenician freighters" in label:
                    m_ph = re.search(r"(\d+)\s*/\s*(\d+)", val_text)
                    if m_ph:
                        if "phoenicianFreightersBought" not in td:
                            self.phoenicianFreightersBought = int(m_ph.group(1))
                        if "phoenicianFreightersMax" not in td:
                            self.phoenicianFreightersMax = int(m_ph.group(2))

        cities_meta = td.get("cities") if isinstance(td.get("cities"), dict) else {}
        html_rows_by_id: Dict[int, DockyardCityEntry] = {}
        html_rows_order: List[DockyardCityEntry] = []

        dock_tbl = soup.select_one("#mainview table.dockyardList, #warehouseList")
        if dock_tbl is not None:
            for tr in dock_tbl.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 3:
                    continue
                link = cells[0].find("a")
                cid = 0
                if link is not None and link.get("onclick"):
                    m_cid = re.search(r"value\s*=\s*(\d+)", str(link["onclick"]))
                    if m_cid:
                        cid = int(m_cid.group(1))
                city_name, x, y = parse_labeled_coords(cells[0].get_text(" ", strip=True))
                dock_lvl = parse_int(cells[1].get_text(strip=True)) or 0
                status_text = " ".join(cells[2].get_text(" ", strip=True).split())
                buy_link = cells[2].find("a", href=True)
                buy_url = (
                    str(buy_link["href"])
                    if buy_link is not None and buy_link.get("href") not in (None, "", "#")
                    else None
                )
                entry = DockyardCityEntry(
                    cityId=cid,
                    cityName=city_name,
                    x=x,
                    y=y,
                    dockyardLevel=dock_lvl,
                    statusText=status_text,
                    canBuyHere=buy_link is not None,
                    buyUrl=buy_url,
                )
                html_rows_order.append(entry)
                if cid:
                    html_rows_by_id[cid] = entry

        if cities_meta:
            for cid_str, meta in cities_meta.items():
                cid = parse_int(cid_str) or 0
                if not isinstance(meta, dict):
                    continue
                name, x, y = parse_labeled_coords(str(meta.get("name") or ""))
                dock_lvl = parse_int(meta.get("dockyardLevel")) or 0
                port_pos = parse_int(meta.get("portPosition"))
                html_match = html_rows_by_id.get(cid)
                self.cities.append(
                    DockyardCityEntry(
                        cityId=cid,
                        cityName=name,
                        x=x,
                        y=y,
                        dockyardLevel=dock_lvl,
                        portPosition=port_pos,
                        statusText=html_match.statusText if html_match else "",
                        canBuyHere=html_match.canBuyHere if html_match else False,
                        buyUrl=html_match.buyUrl if html_match else None,
                    )
                )
        else:
            self.cities = html_rows_order

        self.totalDockyardLevels = sum(entry.dockyardLevel for entry in self.cities)
        self.maxNormalFreighters = (
            self.purchasedFreighters + self.freightersRemainingToBuy
            if ("boughtNormalFreighters" in td or "freightersStillToBeBought" in td)
            else self.totalDockyardLevels
        )

    async def buyFreighter(self) -> Any:
        """Purchase a freighter if capacity is available."""
        ...

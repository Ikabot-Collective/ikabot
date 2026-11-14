"""Model for the Ikariam Sea Chart Archive building (``view=marineChartArchive``)."""

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    make_soup,
    parse_int,
)
from ikabot.ikariam.buildings._base import (
    Building,
    parse_duration_seconds,
    tmpl_text,
)
from ikabot.ikariam.data import Unit, Units

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


def _parse_signed_duration_seconds(text: str) -> Optional[int]:
    """Parse an Ikariam duration string preserving a leading minus sign."""
    stripped = text.strip()
    if not stripped:
        return None
    secs = parse_duration_seconds(stripped)
    if secs is None:
        return None
    return -secs if stripped.startswith("-") else secs


@dataclass
class MarineChartShipOption:
    """Selectable ship type in the Sea Chart Archive dropdown."""

    shipId: int
    name: str
    unit: Optional[Unit]
    isSelected: bool = False


@dataclass
class MarineChartBenchmark:
    """Example travel time and Sea Chart Archive reduction at a fixed island distance."""

    distanceIslands: int
    currentDurationText: str
    currentDurationSeconds: int
    nextLevelDeltaText: str
    nextLevelDeltaSeconds: int
    currentSavingText: str
    currentSavingSeconds: int
    withoutArchiveDurationSeconds: int
    reductionPercent: float


class MarineChartArchive(Building):
    """Sea Chart Archive view model with ship selection and travel-time reduction examples."""

    selectedShipId: Optional[int]
    selectedShipName: str
    selectedShip: Optional[Unit]
    availableShips: List[MarineChartShipOption]
    benchmarks: List[MarineChartBenchmark]
    nextLevelDescription: str

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a Sea Chart Archive building model without making HTTP requests."""
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        if not self.buildingType:
            self.buildingType = "marineChartArchive"
        self._reset_fields()

    def _reset_fields(self) -> None:
        """Reset view-specific attributes before parsing a Sea Chart Archive payload."""
        self.selectedShipId = None
        self.selectedShipName = ""
        self.selectedShip = None
        self.availableShips = []
        self.benchmarks = []
        self.nextLevelDescription = ""

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Extract selectable ship options, selected ship, and distance travel benchmarks."""
        self._reset_fields()

        options_html = resp.template_data.get("js_selectedShip")
        if isinstance(options_html, str) and options_html.strip():
            option_tags = make_soup(options_html).find_all("option")
        else:
            select_tag = soup.find(id="js_selectedShip")
            option_tags = select_tag.find_all("option") if select_tag is not None else []

        for opt in option_tags:
            ship_id = parse_int(opt.get("value"))
            if ship_id is None:
                continue
            name = opt.get_text(" ", strip=True)
            is_sel = opt.has_attr("selected")
            unit_tpl = Units.getUnitById(ship_id)
            self.availableShips.append(
                MarineChartShipOption(
                    shipId=ship_id,
                    name=name,
                    unit=unit_tpl,
                    isSelected=is_sel,
                )
            )
            if is_sel or self.selectedShipId is None:
                if is_sel or not self.selectedShipName:
                    self.selectedShipId = ship_id
                    self.selectedShipName = name
                    self.selectedShip = unit_tpl

        distances: List[int] = []
        for key in resp.template_data:
            m_dist = re.fullmatch(r"js_example(\d+)_time_current", key)
            if m_dist:
                distances.append(int(m_dist.group(1)))
        for span in soup.select("[id^='js_example'][id$='_time_current']"):
            m_dist = re.fullmatch(r"js_example(\d+)_time_current", str(span.get("id") or ""))
            if m_dist:
                dist = int(m_dist.group(1))
                if dist not in distances:
                    distances.append(dist)
        distances.sort()

        for dist in distances:
            cur_text = self._read_field(soup, resp, f"js_example{dist}_time_current")
            next_text = self._read_field(soup, resp, f"js_example{dist}_time_next_delta")
            without_text = self._read_field(
                soup, resp, f"js_example{dist}_time_without_delta"
            )
            cur_secs = parse_duration_seconds(cur_text) or 0
            next_secs = _parse_signed_duration_seconds(next_text) or 0
            saving_secs = _parse_signed_duration_seconds(without_text) or 0
            base_secs = cur_secs + abs(saving_secs) if saving_secs <= 0 else cur_secs
            reduction_pct = (
                round(abs(saving_secs) / base_secs * 100.0, 2) if base_secs > 0 else 0.0
            )
            self.benchmarks.append(
                MarineChartBenchmark(
                    distanceIslands=dist,
                    currentDurationText=cur_text,
                    currentDurationSeconds=cur_secs,
                    nextLevelDeltaText=next_text,
                    nextLevelDeltaSeconds=next_secs,
                    currentSavingText=without_text,
                    currentSavingSeconds=saving_secs,
                    withoutArchiveDurationSeconds=base_secs,
                    reductionPercent=reduction_pct,
                )
            )

        self.nextLevelDescription = tmpl_text(resp, "nextLevelDesc")

    @staticmethod
    def _read_field(soup: BeautifulSoup, resp: AjaxResponse, key: str) -> str:
        """Read benchmark string from ``template_data[key]`` or HTML span ``#key``."""
        text = tmpl_text(resp, key)
        if text:
            return text
        tag = soup.find(id=key)
        return tag.get_text(" ", strip=True) if tag is not None else ""

    def getBenchmark(self, distanceIslands: int) -> Optional[MarineChartBenchmark]:
        """Return the parsed benchmark for ``distanceIslands`` if present."""
        for bm in self.benchmarks:
            if bm.distanceIslands == distanceIslands:
                return bm
        return None

    async def selectShip(self, shipId: Union[int, Unit]) -> "MarineChartArchive":
        """Select ``shipId`` to preview Sea Chart Archive travel-time reductions."""
        client = self._require_client()
        if self.position is None:
            raise ValueError("MarineChartArchive position is required to select a ship")
        resolved_id = shipId.id if isinstance(shipId, Unit) else int(shipId)
        resp = await client.get_ajax(
            params={
                "view": "noViewChange",
                "templateView": "marineChartArchive",
                "cityId": str(self.cityId),
                "position": str(self.position),
                "ship": str(resolved_id),
            }
        )
        if resp.view_html:
            self.parseView(resp)
        else:
            self._last_response = resp
            self._parse_body(make_soup(""), resp)
        return self

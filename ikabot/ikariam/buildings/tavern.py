"""Model for the Ikariam Tavern building (``view=tavern``)."""

from dataclasses import dataclass
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    parse_float,
    parse_int,
)
from ikabot.ikariam.buildings._base import (
    Building,
    tmpl_text,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


@dataclass
class TavernWineLevel:
    """Wine serving level option with hourly consumption, savings, and happiness effect."""

    level: int
    winePerHour: int
    savedWinePerHour: float
    satisfactionBonus: int
    growthRate: Optional[float] = None


class Tavern(Building):
    """Tavern view model with wine serving levels, satisfaction bonus, and growth rates."""

    wineServeLevel: int
    maxWineServeLevel: int
    winePerHour: int
    savedWinePerHour: float
    satisfactionBonus: int
    baseSatisfaction: int
    currentSatisfaction: int
    happinessStatus: str
    growthRate: float
    resourceBonusFactor: float
    corruptionFactor: float
    wineOptions: Dict[int, int]
    wineLevels: List[TavernWineLevel]

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a Tavern building model without making HTTP requests."""
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        if not self.buildingType:
            self.buildingType = "tavern"
        self._reset_fields()

    def _reset_fields(self) -> None:
        """Reset view-specific attributes before parsing a Tavern payload."""
        self.wineServeLevel = 0
        self.maxWineServeLevel = 0
        self.winePerHour = 0
        self.savedWinePerHour = 0.0
        self.satisfactionBonus = 0
        self.baseSatisfaction = 0
        self.currentSatisfaction = 0
        self.happinessStatus = ""
        self.growthRate = 0.0
        self.resourceBonusFactor = 0.0
        self.corruptionFactor = 1.0
        self.wineOptions = {}
        self.wineLevels = []

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Extract served wine level, per-level options, satisfaction, and growth rate."""
        self._reset_fields()

        sat_entry = resp.template_data.get("citySatisfaction")
        if isinstance(sat_entry, dict) and sat_entry.get("class"):
            self.happinessStatus = str(sat_entry.get("class") or "").strip()

        growth_text = tmpl_text(resp, "js_TavernPopulationGrowthValue")
        if not growth_text:
            growth_el = soup.find(id="js_TavernPopulationGrowthValue")
            growth_text = growth_el.get_text(" ", strip=True) if growth_el is not None else ""
        growth_val = parse_float(growth_text)
        self.growthRate = 0.0 if growth_val in (None, 0.0) else growth_val

        selected_from_html: Optional[int] = None
        wine_select = soup.find(id="wineAmount")
        if wine_select is not None:
            for opt in wine_select.find_all("option"):
                lvl = parse_int(opt.get("value"))
                if lvl is None:
                    continue
                if opt.has_attr("selected"):
                    selected_from_html = lvl
                opt_text = opt.get_text(" ", strip=True)
                m_amount = re.match(r"^\s*(\d+)", opt_text)
                self.wineOptions[lvl] = int(m_amount.group(1)) if m_amount else 0

        if self.wineOptions:
            self.maxWineServeLevel = max(self.wineOptions.keys())

        sat_per_wine: List[int] = []
        saved_wine: List[float] = []
        growth_per_level: List[Optional[float]] = []

        load_js = resp.template_data.get("load_js")
        if isinstance(load_js, dict) and isinstance(load_js.get("params"), str):
            try:
                js_params = json.loads(load_js["params"], strict=False)
            except (ValueError, TypeError):
                js_params = {}
            if isinstance(js_params, dict):
                bld_lvl = parse_int(js_params.get("buildingLevel"))
                if bld_lvl is not None and not self.level:
                    self.level = bld_lvl
                serve_lvl = parse_int(js_params.get("wineServeLevel"))
                if serve_lvl is not None:
                    self.wineServeLevel = serve_lvl
                start_sat = parse_int(js_params.get("startSatisfaction"))
                if start_sat is not None:
                    self.baseSatisfaction = start_sat
                res_factor = parse_float(js_params.get("resourceBonusFactor"))
                if res_factor is not None:
                    self.resourceBonusFactor = res_factor
                corr_factor = parse_float(js_params.get("corruptionFactor"))
                if corr_factor is not None:
                    self.corruptionFactor = corr_factor

                if isinstance(js_params.get("satPerWine"), list):
                    sat_per_wine = [parse_int(v) or 0 for v in js_params["satPerWine"]]
                if isinstance(js_params.get("savedWine"), list):
                    saved_wine = [parse_float(v) or 0.0 for v in js_params["savedWine"]]
                if isinstance(js_params.get("growthPerWineLevel"), list):
                    for item in js_params["growthPerWineLevel"]:
                        raw_val = item.get("value") if isinstance(item, dict) else item
                        val = parse_float(raw_val)
                        growth_per_level.append(0.0 if val == 0.0 else val)

        if self.wineServeLevel == 0 and selected_from_html is not None:
            self.wineServeLevel = selected_from_html

        max_lvl = max(
            self.maxWineServeLevel,
            len(sat_per_wine) - 1 if sat_per_wine else 0,
        )
        self.maxWineServeLevel = max_lvl

        for lvl in range(max_lvl + 1):
            wine_hr = self.wineOptions.get(lvl, 0)
            saved_hr = saved_wine[lvl] if lvl < len(saved_wine) else 0.0
            sat_val = sat_per_wine[lvl] if lvl < len(sat_per_wine) else 0
            g_val = growth_per_level[lvl] if lvl < len(growth_per_level) else None
            self.wineLevels.append(
                TavernWineLevel(
                    level=lvl,
                    winePerHour=wine_hr,
                    savedWinePerHour=saved_hr,
                    satisfactionBonus=sat_val,
                    growthRate=g_val,
                )
            )

        self.winePerHour = self.wineOptions.get(self.wineServeLevel, 0)
        if 0 <= self.wineServeLevel < len(saved_wine):
            self.savedWinePerHour = saved_wine[self.wineServeLevel]
        else:
            saved_el = soup.find(id="savedWine")
            self.savedWinePerHour = (
                parse_float(saved_el.get_text(strip=True)) if saved_el is not None else 0.0
            ) or 0.0

        if 0 <= self.wineServeLevel < len(sat_per_wine):
            self.satisfactionBonus = sat_per_wine[self.wineServeLevel]
        else:
            bonus_el = soup.find(id="bonus")
            self.satisfactionBonus = (
                parse_int(bonus_el.get_text(strip=True)) if bonus_el is not None else 0
            ) or 0

        self.currentSatisfaction = self.baseSatisfaction + self.satisfactionBonus

    async def serveWine(self, level: int) -> "Tavern":
        """Set the Tavern's hourly wine serving level to ``level``."""
        await self._post_building_action(
            action="CityScreen",
            function="assignWinePerTick",
            payloadPost={"amount": str(int(level))},
            action_name="Tavern.serveWine",
        )
        return self

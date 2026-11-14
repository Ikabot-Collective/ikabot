"""Model for the Ikariam Academy building (``view=academy``)."""

import json
import re
from typing import TYPE_CHECKING, Any, Dict, Optional

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    parse_float,
    parse_int,
)
from ikabot.ikariam.buildings._base import (
    Building,
    tmpl_int,
    tmpl_text,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


def _clean_float(value: Any) -> Optional[float]:
    """Parse a float while normalizing negative zero and float representation noise."""
    parsed = parse_float(value)
    if parsed is None:
        return None
    rounded = round(parsed, 6)
    return 0.0 if rounded == 0.0 else rounded


class Academy(Building):
    """Academy view model covering scientist assignments, research output, and experiments."""

    citizens: int
    scientists: int
    maxScientists: int
    maxOvercharge: int
    isOvercharged: bool

    researchProduction: int
    basicResearchProduction: float
    researchProductionFactor: float
    costPerScientist: int
    townIncome: Optional[int]

    worldBonusPercent: float
    premiumBonusPercent: float
    researchBonusPercent: float
    governmentBonusPercent: float
    corruptionPenaltyPercent: float

    hasAthenaScroll: bool
    isAthenaScrollActive: bool
    athenaScrollAmbrosiaPrice: Optional[int]

    experimentResearchPoints: Optional[int]
    experimentCrystalCost: Optional[int]
    experimentDiscountedCrystalCost: Optional[int]
    experimentOnCooldown: bool
    canConductExperiment: bool

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize an Academy building model without making HTTP requests."""
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        if not self.buildingType:
            self.buildingType = "academy"
        self._reset_fields()

    def _reset_fields(self) -> None:
        """Reset view-specific attributes before parsing an Academy payload."""
        self.citizens = 0
        self.scientists = 0
        self.maxScientists = 0
        self.maxOvercharge = 0
        self.isOvercharged = False

        self.researchProduction = 0
        self.basicResearchProduction = 0.0
        self.researchProductionFactor = 1.0
        self.costPerScientist = 0
        self.townIncome = None

        self.worldBonusPercent = 0.0
        self.premiumBonusPercent = 0.0
        self.researchBonusPercent = 0.0
        self.governmentBonusPercent = 0.0
        self.corruptionPenaltyPercent = 0.0

        self.hasAthenaScroll = False
        self.isAthenaScrollActive = False
        self.athenaScrollAmbrosiaPrice = None

        self.experimentResearchPoints = None
        self.experimentCrystalCost = None
        self.experimentDiscountedCrystalCost = None
        self.experimentOnCooldown = False
        self.canConductExperiment = False

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Extract scientist slider limits, research production breakdown, and experiment status."""
        self._reset_fields()

        citizens_val = tmpl_int(resp, "valueCitizens")
        if citizens_val is None:
            tag = soup.find(id="valueCitizens")
            citizens_val = parse_int(tag.get_text(strip=True)) if tag is not None else None
        self.citizens = citizens_val or 0

        workers_val = tmpl_int(resp, "valueWorkers")
        if workers_val is None:
            tag = soup.find(id="valueWorkers")
            workers_val = parse_int(tag.get_text(strip=True)) if tag is not None else None
        self.scientists = workers_val or 0

        income_val = tmpl_int(resp, "valueWorkCosts")
        if income_val is None:
            tag = soup.find(id="valueWorkCosts")
            income_val = parse_int(tag.get_text(strip=True)) if tag is not None else None
        self.townIncome = income_val

        slider_entry = resp.template_data.get("js_AcademySlider")
        slider = slider_entry.get("slider") if isinstance(slider_entry, dict) else None
        if isinstance(slider, dict):
            self.maxScientists = parse_int(slider.get("max_value")) or 0
            self.maxOvercharge = parse_int(slider.get("overcharge")) or 0
            ini_val = parse_int(slider.get("ini_value"))
            if ini_val is not None and workers_val is None:
                self.scientists = ini_val
            cb = slider.get("callback_data")
            if isinstance(cb, dict):
                factor = _clean_float(cb.get("researchProductionFactor"))
                if factor is not None:
                    self.researchProductionFactor = factor
                cost_per = parse_int(cb.get("costPerScientist"))
                if cost_per is not None:
                    self.costPerScientist = cost_per
                if self.townIncome is None:
                    self.townIncome = parse_int(cb.get("startIncomePerTimeUnit"))
        else:
            max_link = soup.select_one("#js_AcademySlider a.setMax")
            if max_link is not None:
                m_max = re.search(r"setActualValue\((\d+)\)", str(max_link.get("onclick") or ""))
                if m_max:
                    self.maxScientists = int(m_max.group(1))

        self.isOvercharged = self.scientists > self.maxScientists

        load_js = resp.template_data.get("load_js")
        if isinstance(load_js, dict) and isinstance(load_js.get("params"), str):
            try:
                js_params = json.loads(load_js["params"], strict=False)
            except (ValueError, TypeError):
                js_params = {}
            if isinstance(js_params, dict):
                factor = _clean_float(js_params.get("researchProductionFactor"))
                if factor is not None:
                    self.researchProductionFactor = factor
                self.hasAthenaScroll = bool(js_params.get("hasAthenaScroll", False))
                self.isAthenaScrollActive = bool(js_params.get("isAthenaScrollActive", False))
                self.athenaScrollAmbrosiaPrice = parse_int(js_params.get("itemAmbrosiaPrice"))

        self._parse_research_breakdown(soup, resp)
        self._parse_experiment(soup)

    def _parse_research_breakdown(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse hourly research point totals and percentage modifiers."""
        total_val = tmpl_int(resp, "js_academy_research_tooltip_total_production")
        if total_val is None:
            tag = soup.find(id="js_academy_research_tooltip_total_production") or soup.find(
                id="valueResearch"
            )
            total_val = parse_int(tag.get_text(strip=True)) if tag is not None else None
        self.researchProduction = total_val or 0

        basic_text = tmpl_text(resp, "js_academy_research_tooltip_basic_production")
        if not basic_text:
            tag = soup.find(id="js_academy_research_tooltip_basic_production")
            basic_text = tag.get_text(strip=True) if tag is not None else ""
        self.basicResearchProduction = _clean_float(basic_text) or 0.0

        world_text = tmpl_text(resp, "js_academy_research_tooltip_world_bonus")
        if not world_text:
            tag = soup.find(id="js_academy_research_tooltip_world_bonus")
            world_text = tag.get_text(strip=True) if tag is not None else ""
        world_val = _clean_float(world_text)
        if world_val is not None:
            self.worldBonusPercent = world_val

        tbl = soup.select_one("table.breakdown_table")
        if tbl is None:
            return
        for tr in tbl.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            label = tds[0].get_text(" ", strip=True).rstrip(":").strip().lower()
            val = _clean_float(tds[1].get_text(" ", strip=True))
            if val is None or not label:
                continue
            if label == "basic production" and not basic_text:
                self.basicResearchProduction = val
            elif label == "world" and not world_text:
                self.worldBonusPercent = val
            elif label == "premium bonus":
                self.premiumBonusPercent = val
            elif label == "research":
                self.researchBonusPercent = val
            elif label == "form of government":
                self.governmentBonusPercent = val
            elif label == "corruption":
                self.corruptionPenaltyPercent = abs(val)
            elif label == "total" and total_val is None:
                self.researchProduction = int(round(val))

    def _parse_experiment(self, soup: BeautifulSoup) -> None:
        """Parse the crystal experiment achievement, crystal cost, and cooldown state."""
        accel = soup.find(id="accelerateResearch")
        self.experimentOnCooldown = (
            soup.find(id=re.compile(r"experimentCooldown", re.IGNORECASE)) is not None
            or soup.select_one(".experimentCooldown") is not None
            or "experimentCooldown" in str(soup)
        )
        if accel is None:
            return

        ach = accel.select_one(".research-achievement .achievement-content")
        if ach is not None:
            for span in ach.find_all("span"):
                val = parse_int(span.get_text(strip=True))
                if val is not None:
                    self.experimentResearchPoints = val
                    break

        options = accel.select(".experiment-options .experiment")
        if options:
            for span in options[0].select(".cost-info span"):
                val = parse_int(span.get_text(strip=True))
                if val is not None:
                    self.experimentCrystalCost = val
                    break
            if len(options) >= 2:
                disc = options[1].select_one(".discounted-cost")
                if disc is not None:
                    self.experimentDiscountedCrystalCost = parse_int(disc.get_text(strip=True))

        has_button = accel.select_one("input[onclick*='conductExperiment']") is not None
        self.canConductExperiment = has_button and not self.experimentOnCooldown

    async def assignScientists(self, scientists: int) -> "Academy":
        """Assign ``scientists`` to work in this Academy."""
        await self._post_building_action(
            action="IslandScreen",
            function="workerPlan",
            payloadPost={"screen": "academy", "s": str(int(scientists))},
            action_name="Academy.assignScientists",
        )
        return self

    async def conductExperiment(
        self,
        useAthenaScroll: bool = False,
        payWithAmbrosia: bool = False,
    ) -> "Academy":
        """Conduct a crystal experiment in this Academy."""
        if not self.isLoaded:
            await self.load()
        if self.experimentOnCooldown or not self.canConductExperiment:
            raise ValueError(
                f"Academy@{self.cityId} cannot conduct an experiment right now "
                f"(onCooldown={self.experimentOnCooldown}, canConduct={self.canConductExperiment})"
            )

        ambrosia_cost = 0
        if payWithAmbrosia:
            ambrosia_cost = 10
        elif useAthenaScroll:
            has_scroll = False
            tmpl = (
                self._last_response.template_data
                if self._last_response is not None and isinstance(self._last_response.template_data, dict)
                else {}
            )
            load_js = tmpl.get("load_js") if isinstance(tmpl.get("load_js"), dict) else {}
            raw_params = load_js.get("params") if isinstance(load_js, dict) else None
            if isinstance(raw_params, str) and raw_params:
                try:
                    parsed = json.loads(raw_params)
                    has_scroll = bool(
                        parsed.get("hasAthenaScroll") or parsed.get("isAthenaScrollActive")
                    )
                except ValueError:
                    has_scroll = False
            if not has_scroll:
                ambrosia_cost = 10

        resp = await self._post_building_action(
            action="CityScreen",
            function="buyResearch",
            payloadPost={
                "useAthenasScroll": "1" if useAthenaScroll else "0",
                "payWithAmbrosia": "1" if payWithAmbrosia else "0",
            },
            action_name="Academy.conductExperiment",
            metadata={
                "ambrosia_cost": ambrosia_cost,
                "cityId": self.cityId,
                "useAthenaScroll": useAthenaScroll,
            },
            refresh=False,
        )
        if resp.view_html and ("accelerateResearch" in resp.view_html or "experimentCooldown" in resp.view_html):
            self.parseView(resp)
        else:
            await self.load()
        return self

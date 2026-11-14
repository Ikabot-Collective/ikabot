"""Model for the Ikariam Town Hall building (``view=townHall``)."""

from dataclasses import dataclass, field
import json
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    make_soup,
    parse_float,
    parse_int,
)
from ikabot.ikariam.buildings._base import (
    Building,
    tmpl_int,
    tmpl_text,
    tmpl_value,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


_LUXURY_CLASS_MAP = {
    "wood": "wood",
    "wine": "wine",
    "marble": "marble",
    "crystal": "crystal",
    "glass": "crystal",
    "sulfur": "sulphur",
    "sulphur": "sulphur",
}


def _parse_split_worker_text(text: str) -> Tuple[int, int, int]:
    """Parse ``'990 + 495'`` or ``'824'`` into ``(total, standard, overload)``."""
    parts = [parse_int(p) for p in text.split("+")]
    nums = [p for p in parts if p is not None]
    if not nums:
        return 0, 0, 0
    if len(nums) == 1:
        return nums[0], nums[0], 0
    return sum(nums), nums[0], sum(nums[1:])


def _element_has_class(
    soup: BeautifulSoup,
    resp: AjaxResponse,
    key: str,
    class_name: str,
) -> Optional[bool]:
    """Check whether ``key`` has ``class_name`` via ``template_data`` or ``soup``."""
    entry = resp.template_data.get(key)
    if isinstance(entry, dict) and "class" in entry:
        classes = str(entry.get("class") or "").split()
        return class_name in classes
    tag = soup.find(id=key)
    if tag is not None:
        return class_name in (tag.get("class") or [])
    return None


def _read_text(soup: BeautifulSoup, resp: AjaxResponse, key: str) -> str:
    """Read text for ``key`` preferring ``template_data`` and falling back to ``soup``."""
    text = tmpl_text(resp, key)
    if text:
        return text
    tag = soup.find(id=key)
    return tag.get_text(" ", strip=True) if tag is not None else ""


def _read_int(soup: BeautifulSoup, resp: AjaxResponse, key: str) -> Optional[int]:
    """Read an integer for ``key`` preferring ``template_data`` and falling back to ``soup``."""
    val = tmpl_int(resp, key)
    if val is not None:
        return val
    tag = soup.find(id=key)
    return parse_int(tag.get_text(" ", strip=True)) if tag is not None else None


@dataclass
class TownHallSatisfaction:
    """Breakdown of satisfaction bonuses and deductions in the Town Hall."""

    baseBonus: int = 0
    governmentBonus: int = 0
    researchBonus: int = 0
    capitalBonus: int = 0
    eventBonus: int = 0
    transferBonus: int = 0
    tavernBonus: int = 0
    wineServeBonus: int = 0
    museumBonus: int = 0
    culturalTreatyBonus: int = 0

    populationDeduction: int = 0
    corruptionDeduction: int = 0
    revoltDeduction: int = 0
    governmentDeduction: int = 0

    totalSatisfaction: int = 0
    happinessStatus: str = ""
    hasTavern: bool = False
    hasMuseum: bool = False


class TownHall(Building):
    """Town Hall view model with population, production, income, and satisfaction stats."""

    cityTitle: str
    displayedCityName: str
    isCapital: bool
    isColony: bool

    occupiedSpace: int
    maxInhabitants: int
    garrisonLimitLand: int
    garrisonLimitSea: int
    actionPointsAvailable: int
    maxActionPoints: int

    growthRate: float
    netGold: int
    corruptionPercent: float
    happinessStatus: str
    totalSatisfaction: int
    plunderSafeCapacity: int

    citizens: int
    woodWorkers: int
    woodWorkersStandard: int
    woodWorkersOverload: int
    luxuryWorkers: int
    luxuryWorkersStandard: int
    luxuryWorkersOverload: int
    scientists: int
    priests: int

    maxWoodWorkers: int
    maxLuxuryWorkers: int
    maxScientists: int
    maxPriests: int
    canAssignScientists: bool
    canAssignPriests: bool

    luxuryResourceType: Optional[str]
    woodProduction: int
    luxuryProduction: int
    scientistsResearchProduction: int
    scientistsGoldCost: int
    woodWorkerGoldCost: int
    luxuryWorkerGoldCost: int
    priestsGoldProduction: int
    citizensGoldProduction: int
    productionFactors: Dict[str, float]

    notices: List[str]
    satisfaction: TownHallSatisfaction
    cityIcons: List[Dict[str, Any]]

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a Town Hall building model without making HTTP requests."""
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        if not self.buildingType:
            self.buildingType = "townHall"
        self._reset_fields()

    def _reset_fields(self) -> None:
        """Reset view-specific attributes before parsing a Town Hall payload."""
        self.cityTitle = ""
        self.displayedCityName = ""
        self.isCapital = False
        self.isColony = False

        self.occupiedSpace = 0
        self.maxInhabitants = 0
        self.garrisonLimitLand = 0
        self.garrisonLimitSea = 0
        self.actionPointsAvailable = 0
        self.maxActionPoints = 0

        self.growthRate = 0.0
        self.netGold = 0
        self.corruptionPercent = 0.0
        self.happinessStatus = ""
        self.totalSatisfaction = 0
        self.plunderSafeCapacity = 0

        self.citizens = 0
        self.woodWorkers = 0
        self.woodWorkersStandard = 0
        self.woodWorkersOverload = 0
        self.luxuryWorkers = 0
        self.luxuryWorkersStandard = 0
        self.luxuryWorkersOverload = 0
        self.scientists = 0
        self.priests = 0

        self.maxWoodWorkers = 0
        self.maxLuxuryWorkers = 0
        self.maxScientists = 0
        self.maxPriests = 0
        self.canAssignScientists = False
        self.canAssignPriests = False

        self.luxuryResourceType = None
        self.woodProduction = 0
        self.luxuryProduction = 0
        self.scientistsResearchProduction = 0
        self.scientistsGoldCost = 0
        self.woodWorkerGoldCost = 0
        self.luxuryWorkerGoldCost = 0
        self.priestsGoldProduction = 0
        self.citizensGoldProduction = 0
        self.productionFactors = {}

        self.notices = []
        self.satisfaction = TownHallSatisfaction()
        self.cityIcons = []

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Extract Town Hall city stats, workforce distribution, production, and satisfaction."""
        self._reset_fields()

        title_el = soup.find(id="js_TownHallCityName")
        self.cityTitle = title_el.get_text(" ", strip=True) if title_el is not None else ""
        old_name_el = soup.find(id="js_oldCityName")
        self.displayedCityName = (
            old_name_el.get_text(" ", strip=True) if old_name_el is not None else ""
        )
        self.isColony = soup.find(id="abandonSidebar") is not None

        self.occupiedSpace = _read_int(soup, resp, "js_TownHallOccupiedSpace") or 0
        self.maxInhabitants = _read_int(soup, resp, "js_TownHallMaxInhabitants") or 0
        self.garrisonLimitLand = _read_int(soup, resp, "js_TownHallGarrisonLimitLand") or 0
        self.garrisonLimitSea = _read_int(soup, resp, "js_TownHallGarrisonLimitSea") or 0
        self.actionPointsAvailable = (
            _read_int(soup, resp, "js_TownHallActionPointsAvailable") or 0
        )
        self.maxActionPoints = (
            _read_int(soup, resp, "js_TownHallMaxActionPointsAvailable") or 0
        )

        growth_val = parse_float(_read_text(soup, resp, "js_TownHallPopulationGrowthValue"))
        self.growthRate = 0.0 if growth_val in (None, 0.0) else growth_val
        self.netGold = _read_int(soup, resp, "js_TownHallIncomeGoldValue") or 0
        corr_val = parse_float(_read_text(soup, resp, "js_TownHallCorruption"))
        self.corruptionPercent = 0.0 if corr_val in (None, 0.0) else corr_val

        self.happinessStatus = (
            _read_text(soup, resp, "js_TownHallHappinessLargeText")
            or _read_text(soup, resp, "js_TownHallHappinessSmallText")
        )
        self.totalSatisfaction = _read_int(soup, resp, "js_TownHallHappinessLargeValue") or 0
        self.plunderSafeCapacity = tmpl_int(resp, "js_TownHallPlunderSafeCapacity") or 0

        self._parse_workforce(soup, resp)
        self._parse_notices(soup, resp)
        self._parse_satisfaction(soup, resp)

        icons = resp.template_data.get("cityIcons")
        if isinstance(icons, list):
            self.cityIcons = [dict(item) for item in icons if isinstance(item, dict)]

    def _parse_workforce(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse worker/scientist/priest allocations, caps, and hourly production rates."""
        wood_text = _read_text(soup, resp, "js_TownHallPopulationGraphResourceWorkerCount")
        lux_text = _read_text(soup, resp, "js_TownHallPopulationGraphSpecialWorkerCount")
        wood_tot, wood_std, wood_over = _parse_split_worker_text(wood_text)
        lux_tot, lux_std, lux_over = _parse_split_worker_text(lux_text)

        self.citizens = (
            parse_int(resp.template_data.get("CitizenCount"))
            or _read_int(soup, resp, "js_TownHallPopulationGraphCitizenCount")
            or 0
        )
        self.woodWorkers = (
            parse_int(resp.template_data.get("ResourceWorkerCount"))
            if resp.template_data.get("ResourceWorkerCount") is not None
            else wood_tot
        ) or 0
        self.luxuryWorkers = (
            parse_int(resp.template_data.get("SpecialWorkerCount"))
            if resp.template_data.get("SpecialWorkerCount") is not None
            else lux_tot
        ) or 0
        self.scientists = (
            parse_int(resp.template_data.get("ScientistCount"))
            if resp.template_data.get("ScientistCount") is not None
            else (_read_int(soup, resp, "js_TownHallPopulationGraphScientistCount") or 0)
        ) or 0
        self.priests = (
            parse_int(resp.template_data.get("PriestCount"))
            if resp.template_data.get("PriestCount") is not None
            else (_read_int(soup, resp, "js_TownHallPopulationGraphPriestCount") or 0)
        ) or 0

        self.woodWorkersStandard = wood_std if wood_text else self.woodWorkers
        self.woodWorkersOverload = max(0, self.woodWorkers - self.woodWorkersStandard) if wood_over == 0 else wood_over
        self.luxuryWorkersStandard = lux_std if lux_text else self.luxuryWorkers
        self.luxuryWorkersOverload = max(0, self.luxuryWorkers - self.luxuryWorkersStandard) if lux_over == 0 else lux_over

        load_js = resp.template_data.get("load_js")
        if isinstance(load_js, dict) and isinstance(load_js.get("params"), str):
            try:
                js_params = json.loads(load_js["params"], strict=False)
            except (ValueError, TypeError):
                js_params = {}
            if isinstance(js_params, dict):
                standard = js_params.get("standard")
                if isinstance(standard, dict):
                    std_wood = parse_int(standard.get("Wood"))
                    std_lux = parse_int(standard.get("Luxury"))
                    if std_wood is not None:
                        self.woodWorkersStandard = min(self.woodWorkers, std_wood)
                        self.woodWorkersOverload = max(0, self.woodWorkers - std_wood)
                    if std_lux is not None:
                        self.luxuryWorkersStandard = min(self.luxuryWorkers, std_lux)
                        self.luxuryWorkersOverload = max(0, self.luxuryWorkers - std_lux)
                factors = js_params.get("factors")
                if isinstance(factors, dict):
                    for key, raw_val in factors.items():
                        parsed_factor = parse_float(raw_val)
                        if parsed_factor is not None:
                            self.productionFactors[str(key)] = round(parsed_factor, 6)

        input_specs = (
            ("inputWood", "maxWoodWorkers", None),
            ("inputLuxury", "maxLuxuryWorkers", None),
            ("inputScientists", "maxScientists", "canAssignScientists"),
            ("inputPriests", "maxPriests", "canAssignPriests"),
        )
        for input_id, max_attr, enabled_attr in input_specs:
            inp = soup.find(id=input_id)
            if inp is None:
                continue
            max_val = parse_int(inp.get("data-max") or inp.get("max"))
            if max_val is not None:
                setattr(self, max_attr, max_val)
            if enabled_attr is not None:
                setattr(self, enabled_attr, not inp.has_attr("disabled"))

        lux_icon = soup.select_one("#populationManagement .assignLuxury .resourceIcon")
        if lux_icon is not None:
            for cls in lux_icon.get("class") or []:
                if cls.startswith("icon_"):
                    raw_lux = cls[len("icon_") :].lower()
                    self.luxuryResourceType = _LUXURY_CLASS_MAP.get(raw_lux, raw_lux)
                    break

        self.woodProduction = (
            _read_int(soup, resp, "js_TownHallPopulationGraphWoodProduction") or 0
        )
        self.luxuryProduction = (
            _read_int(soup, resp, "js_TownHallPopulationGraphTradeGoodProduction") or 0
        )
        self.scientistsResearchProduction = (
            _read_int(soup, resp, "js_TownHallPopulationGraphScientistsResearchProduction") or 0
        )
        self.scientistsGoldCost = (
            _read_int(soup, resp, "js_TownHallPopulationGraphScientistsResearchCost") or 0
        )
        self.woodWorkerGoldCost = tmpl_int(resp, "js_TownHallPopulationGraphWoodCost") or 0
        self.luxuryWorkerGoldCost = (
            tmpl_int(resp, "js_TownHallPopulationGraphTradeGoodCost") or 0
        )
        self.priestsGoldProduction = (
            _read_int(soup, resp, "js_TownHallPopulationGraphPriestsGoldProduction") or 0
        )
        self.citizensGoldProduction = (
            _read_int(soup, resp, "js_TownHallPopulationGraphCitizensGoldProduction") or 0
        )

    def _parse_notices(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse warning/incident notices shown in ``#js_TownHallNoticeBox``."""
        notice_entry = resp.template_data.get("js_TownHallNoticeBox")
        if isinstance(notice_entry, dict):
            raw_notices = notice_entry.get("notices")
            if isinstance(raw_notices, list):
                for item in raw_notices:
                    text = make_soup(str(item)).get_text(" ", strip=True)
                    if text:
                        self.notices.append(text)
            if not self.notices and notice_entry.get("class") != "invisible":
                raw_text = str(notice_entry.get("text") or "").strip()
                if raw_text:
                    text = make_soup(raw_text).get_text(" ", strip=True)
                    if text:
                        self.notices.append(text)
            return

        notice_box = soup.find(id="js_TownHallNoticeBox")
        if notice_box is not None and "invisible" not in (notice_box.get("class") or []):
            for line in notice_box.stripped_strings:
                if line:
                    self.notices.append(line)

    def _visible_satisfaction_val(
        self,
        soup: BeautifulSoup,
        resp: AjaxResponse,
        base_key: str,
        container_key: Optional[str] = None,
    ) -> int:
        """Return a satisfaction bonus/malus value only when its widget is visible."""
        if container_key is not None:
            if _element_has_class(soup, resp, container_key, "invisible") is True:
                return 0
        if _element_has_class(soup, resp, base_key, "invisible") is True:
            return 0
        return _read_int(soup, resp, f"{base_key}Value") or 0

    def _parse_satisfaction(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Parse the positive and negative components of city satisfaction."""
        cap_invisible = _element_has_class(
            soup,
            resp,
            "js_TownHallSatisfactionOverviewBaseBoniCapitalBonus",
            "invisible",
        )
        self.isCapital = cap_invisible is False

        no_tavern_invisible = _element_has_class(
            soup,
            resp,
            "js_TownHallSatisfactionOverviewWineNoTavernMessage",
            "invisible",
        )
        no_museum_invisible = _element_has_class(
            soup,
            resp,
            "js_TownHallSatisfactionOverviewCultureNoMuseumMessage",
            "invisible",
        )

        self.satisfaction = TownHallSatisfaction(
            baseBonus=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewBaseBoniBaseBonus"
            ),
            governmentBonus=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewBaseBoniGovernmentBonus"
            ),
            researchBonus=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewBaseBoniResearchBonus"
            ),
            capitalBonus=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewBaseBoniCapitalBonus"
            ),
            eventBonus=self._visible_satisfaction_val(
                soup,
                resp,
                "js_TownHallSatisfactionOverviewBaseBoniHappeningBonus",
                "js_TownHallSatisfactionOverviewBaseBoniHappeningBonusContainer",
            ),
            transferBonus=self._visible_satisfaction_val(
                soup,
                resp,
                "js_TownHallSatisfactionOverviewBaseBoniTransferBonus",
                "js_TownHallSatisfactionOverviewBaseBoniTransferBonusContainer",
            ),
            tavernBonus=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewWineBoniTavernBonus"
            ),
            wineServeBonus=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewWineBoniServeBonus"
            ),
            museumBonus=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewCultureBoniMuseumBonus"
            ),
            culturalTreatyBonus=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewCultureBoniTreatyBonus"
            ),
            populationDeduction=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewOverpopulationMalus"
            ),
            corruptionDeduction=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewCorruptionMalus"
            ),
            revoltDeduction=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewPunishmentMalus"
            ),
            governmentDeduction=self._visible_satisfaction_val(
                soup, resp, "js_TownHallSatisfactionOverviewGovernmentMalus"
            ),
            totalSatisfaction=self.totalSatisfaction,
            happinessStatus=self.happinessStatus,
            hasTavern=bool(no_tavern_invisible),
            hasMuseum=bool(no_museum_invisible),
        )

    async def rename(self, name: str) -> "TownHall":
        """Rename this city to ``name``."""
        new_name = str(name).strip()
        if not new_name:
            raise ValueError("City name cannot be empty")
        await self._post_building_action(
            action="CityScreen",
            function="rename",
            payloadPost={"name": new_name},
            action_name="TownHall.rename",
        )
        if self.city is not None:
            self.city.name = self.displayedCityName or new_name
        return self

    async def assignWorkers(
        self,
        wood: Optional[int] = None,
        luxury: Optional[int] = None,
        scientists: Optional[int] = None,
        priests: Optional[int] = None,
    ) -> "TownHall":
        """Update worker, scientist, and priest assignments from the Town Hall."""
        self._require_client()
        if not self.isLoaded and any(v is None for v in (wood, luxury, scientists, priests)):
            await self.load()

        await self._post_building_action(
            action="IslandScreen",
            function="workerPlan",
            payloadPost={
                "screen": "TownHall",
                "type": "",
                "wood": str(self.woodWorkers if wood is None else int(wood)),
                "luxury": str(self.luxuryWorkers if luxury is None else int(luxury)),
                "scientists": str(self.scientists if scientists is None else int(scientists)),
                "priests": str(self.priests if priests is None else int(priests)),
            },
            action_name="TownHall.assignWorkers",
        )
        return self

    async def changeCityIcon(self, iconType: int, applyToAll: bool = False) -> Any:
        """Change this city's map icon to ``iconType``."""
        ...

    async def abandonColony(self) -> Any:
        """Abandon this colony."""
        ...

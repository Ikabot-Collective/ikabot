"""Model for the Ikariam Temple building (``view=temple``)."""

import re
from typing import TYPE_CHECKING, Any, Dict, Optional

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    parse_float,
    parse_int,
    parse_query_int,
)
from ikabot.ikariam.buildings._base import (
    Building,
    parse_duration_seconds,
    tmpl_text,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


class Temple(Building):
    """Temple view model covering priest assignments, island faith, and miracle status."""

    citizens: int
    priests: int
    maxPriests: int
    ownConversionPercent: float
    islandConversionPercent: float
    townIncome: Optional[int]
    maxCitizensOnIsland: Optional[int]
    maxInhabitants: Optional[int]
    citizensPerPriest: Optional[int]

    miracleId: Optional[int]
    miracleLevel: int
    miracleMaxLevel: Optional[int]
    islandFaithPercent: float
    miracleTitle: str
    miracleName: str
    miracleSubtitle: str
    miracleEffect: str
    miracleDurationText: str
    miracleDurationSeconds: Optional[int]
    miracleCooldownText: str
    miracleCooldownSeconds: Optional[int]
    miracleRemainingCooldownText: Optional[str]
    miracleRemainingCooldownSeconds: Optional[int]
    miracleTargetsText: Optional[str]
    canActivateMiracle: bool
    activateMiracleUrl: Optional[str]
    miracleIslandUrl: Optional[str]
    miracleIslandId: Optional[int]

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a Temple building model without making HTTP requests."""
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        if not self.buildingType:
            self.buildingType = "temple"
        self._reset_fields()

    def _reset_fields(self) -> None:
        """Reset view-specific attributes before parsing a Temple payload."""
        self.citizens = 0
        self.priests = 0
        self.maxPriests = 0
        self.ownConversionPercent = 0.0
        self.islandConversionPercent = 0.0
        self.townIncome = None
        self.maxCitizensOnIsland = None
        self.maxInhabitants = None
        self.citizensPerPriest = None

        self.miracleId = None
        self.miracleLevel = 0
        self.miracleMaxLevel = None
        self.islandFaithPercent = 0.0
        self.miracleTitle = ""
        self.miracleName = ""
        self.miracleSubtitle = ""
        self.miracleEffect = ""
        self.miracleDurationText = ""
        self.miracleDurationSeconds = None
        self.miracleCooldownText = ""
        self.miracleCooldownSeconds = None
        self.miracleRemainingCooldownText = None
        self.miracleRemainingCooldownSeconds = None
        self.miracleTargetsText = None
        self.canActivateMiracle = False
        self.activateMiracleUrl = None
        self.miracleIslandUrl = None
        self.miracleIslandId = None

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Extract priest slider data, conversion rates, faith level, and miracle info."""
        self._reset_fields()

        citizens_el = soup.find(id="valueCitizens")
        self.citizens = (
            parse_int(citizens_el.get_text(strip=True)) if citizens_el is not None else 0
        ) or 0
        priests_el = soup.find(id="valuePriests")
        self.priests = (
            parse_int(priests_el.get_text(strip=True)) if priests_el is not None else 0
        ) or 0
        own_conv_el = soup.find(id="ownConversion")
        self.ownConversionPercent = (
            parse_float(own_conv_el.get_text(strip=True)) if own_conv_el is not None else 0.0
        ) or 0.0
        isl_conv_el = soup.find(id="conversionIsland")
        self.islandConversionPercent = (
            parse_float(isl_conv_el.get_text(strip=True)) if isl_conv_el is not None else 0.0
        ) or 0.0
        costs_el = soup.find(id="valueWorkCosts")
        self.townIncome = (
            parse_int(costs_el.get_text(strip=True)) if costs_el is not None else None
        )

        slider_entry = resp.template_data.get("js_TempleSlider")
        slider = slider_entry.get("slider") if isinstance(slider_entry, dict) else None
        if isinstance(slider, dict):
            self.maxPriests = parse_int(slider.get("max_value")) or 0
            ini_priests = parse_int(slider.get("ini_value"))
            if ini_priests is not None and not self.priests:
                self.priests = ini_priests
            cb = slider.get("callback_data")
            if isinstance(cb, dict):
                self.maxCitizensOnIsland = parse_int(cb.get("max_citizens_on_island"))
                self.maxInhabitants = parse_int(cb.get("max_inhabitants"))
                self.citizensPerPriest = parse_int(cb.get("citizens_per_priest"))
                if self.townIncome is None:
                    self.townIncome = parse_int(cb.get("income"))
        else:
            max_link = soup.select_one("#js_TempleSlider a.setMax")
            if max_link is not None:
                m_max = re.search(r"setActualValue\((\d+)\)", str(max_link.get("onclick") or ""))
                if m_max:
                    self.maxPriests = int(m_max.group(1))

        lvl_el = soup.find(id="wonderLevelDisplay")
        self.miracleLevel = (
            parse_int(lvl_el.get_text(strip=True)) if lvl_el is not None else 0
        ) or 0

        faith_el = soup.find(id="wonderBeliefInfo2") or soup.find(id="wonderBeliefTooltip")
        if faith_el is not None:
            m_faith = re.search(r"(\d+(?:[.,]\d+)?)\s*%", faith_el.get_text(" ", strip=True))
            if m_faith:
                self.islandFaithPercent = parse_float(m_faith.group(1)) or 0.0

        wonder_box = soup.select_one("#mainview .content.wonder")
        if wonder_box is not None:
            for cls in wonder_box.get("class") or []:
                m_wonder = re.fullmatch(r"wonder(\d+)", cls)
                if m_wonder:
                    self.miracleId = int(m_wonder.group(1))
                    break

        self.miracleTitle = self._read_wonder_text(soup, resp, "js_WonderTextHead")
        m_title = re.match(
            r"^(.*?)\s*\(Level\s+(\d+)\s*/\s*(\d+)\)\s*$",
            self.miracleTitle,
            re.IGNORECASE,
        )
        if m_title:
            self.miracleName = m_title.group(1).strip()
            if not self.miracleLevel:
                self.miracleLevel = int(m_title.group(2))
            self.miracleMaxLevel = int(m_title.group(3))
        else:
            self.miracleName = self.miracleTitle

        self.miracleSubtitle = self._read_wonder_text(soup, resp, "js_WonderTextDesc")
        self.miracleEffect = self._read_wonder_text(soup, resp, "js_WonderTextEffect")

        self.miracleDurationText = self._read_wonder_text(
            soup, resp, "js_WonderTextDurationText"
        )
        self.miracleDurationSeconds = parse_duration_seconds(self.miracleDurationText)

        self.miracleCooldownText = self._read_wonder_text(
            soup, resp, "js_WonderTextCooldownText"
        )
        self.miracleCooldownSeconds = parse_duration_seconds(self.miracleCooldownText)

        rem_cd = self._read_wonder_text(soup, resp, "js_WonderTextCooldown")
        self.miracleRemainingCooldownText = rem_cd or None
        self.miracleRemainingCooldownSeconds = parse_duration_seconds(rem_cd) if rem_cd else None

        targets = self._read_wonder_text(soup, resp, "js_WonderTextTargets")
        self.miracleTargetsText = targets or None

        view_btn = resp.template_data.get("js_WonderViewButton")
        if isinstance(view_btn, dict) and view_btn.get("href"):
            self.miracleIslandUrl = str(view_btn["href"])
        else:
            view_a = soup.find(id="js_WonderViewButton")
            if view_a is not None and view_a.get("href"):
                self.miracleIslandUrl = str(view_a["href"])
        self.miracleIslandId = parse_query_int(self.miracleIslandUrl, "islandId")

        act_btn = resp.template_data.get("js_WonderActivateButton")
        if isinstance(act_btn, dict):
            self.canActivateMiracle = act_btn.get("buttonState") == "enabled"
            if act_btn.get("href"):
                self.activateMiracleUrl = str(act_btn["href"])
        else:
            act_a = soup.find(id="js_WonderActivateButton")
            if act_a is not None:
                classes = act_a.get("class") or []
                self.canActivateMiracle = "disabled" not in classes
                if act_a.get("href"):
                    self.activateMiracleUrl = str(act_a["href"])

    @staticmethod
    def _read_wonder_text(soup: BeautifulSoup, resp: AjaxResponse, key: str) -> str:
        """Read wonder text from ``template_data[key]`` or fallback element ``#key``."""
        text = tmpl_text(resp, key)
        if text:
            return text
        tag = soup.find(id=key)
        return tag.get_text(" ", strip=True) if tag is not None else ""

    async def assignPriests(self, priests: int) -> "Temple":
        """Assign ``priests`` to work in this Temple."""
        await self._post_building_action(
            action="CityScreen",
            function="assignPriests",
            payloadPost={"priests": str(int(priests))},
            action_name="Temple.assignPriests",
        )
        return self

    async def activateMiracle(self) -> "Temple":
        """Activate this island's miracle from the Temple."""
        if not self.isLoaded:
            await self.load()
        if not self.canActivateMiracle or not self.activateMiracleUrl:
            cooldown = self.miracleRemainingCooldownText or "unavailable"
            raise ValueError(
                f"Miracle {self.miracleName!r} in city {self.cityId} cannot be activated ({cooldown})"
            )

        resp = await self._post_query_url_action(
            self.activateMiracleUrl,
            action_name="Temple.activateMiracle",
            templateView="temple",
            metadata={"ambrosia_cost": 0, "cityId": self.cityId, "miracleId": self.miracleId},
            refresh=False,
        )
        if resp.view_html and "wonder" in resp.view_html:
            self.parseView(resp)
        else:
            await self.load()
        return self

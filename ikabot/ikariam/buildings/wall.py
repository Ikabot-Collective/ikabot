"""Model for the Ikariam Town Wall building (``view=wall``)."""

import re
from typing import TYPE_CHECKING, Any, Dict, Optional

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    parse_float,
    parse_int,
)
from ikabot.ikariam.buildings._base import Building

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


class Wall(Building):
    """Town Wall view model with defensive weapon stats, hit points, armour, and breach state."""

    weaponName: str
    damage: int
    accuracyPercent: float
    hitPoints: int
    armour: int
    garrisonLimit: int
    isBreached: bool
    breachInfo: Optional[str]

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a Town Wall building model without making HTTP requests."""
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        if not self.buildingType:
            self.buildingType = "wall"
        self._reset_fields()

    def _reset_fields(self) -> None:
        """Reset view-specific attributes before parsing a Town Wall payload."""
        self.weaponName = ""
        self.damage = 0
        self.accuracyPercent = 0.0
        self.hitPoints = 0
        self.armour = 0
        self.garrisonLimit = 0
        self.isBreached = False
        self.breachInfo = None

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Extract Town Wall combat statistics and breach status from ``#mainview``."""
        self._reset_fields()

        box = soup.select_one("#mainview .highlightbox")
        if box is None:
            return

        weapon_div = box.select_one(".weapon")
        if weapon_div is not None:
            bold_name = weapon_div.find("div", class_="bold")
            if bold_name is not None:
                self.weaponName = bold_name.get_text(" ", strip=True)
            for row in weapon_div.find_all("div", recursive=False):
                if "bold" in (row.get("class") or []):
                    continue
                label_div = row.find("div", class_="floatleft")
                if label_div is None:
                    continue
                label = label_div.get_text(" ", strip=True).lower()
                if "damage" in label:
                    b_tag = row.find("b")
                    self.damage = (parse_int(b_tag.get_text(strip=True)) if b_tag else 0) or 0
                elif "accuracy" in label:
                    acc_container = row.select_one(".damageFocusContainer")
                    raw_acc = str(acc_container.get("title") or "") if acc_container else ""
                    if not raw_acc:
                        bar = row.select_one(".damageFocus")
                        m_width = re.search(
                            r"width\s*:\s*([\d.,]+)\s*%",
                            str(bar.get("style") or "") if bar else "",
                        )
                        raw_acc = m_width.group(1) if m_width else ""
                    self.accuracyPercent = parse_float(raw_acc) or 0.0

        for row in box.find_all("div", recursive=False):
            if "weapon" in (row.get("class") or []):
                continue
            label_div = row.find("div", class_="floatleft")
            if label_div is None:
                continue
            label = label_div.get_text(" ", strip=True).lower()
            b_tag = row.find("b")
            val = parse_int(b_tag.get_text(strip=True)) if b_tag is not None else None
            if val is None:
                continue
            if "hit points" in label:
                self.hitPoints = val
            elif "armour" in label or "armor" in label:
                self.armour = val
            elif "garrison" in label:
                self.garrisonLimit = val

        breach_el = soup.select_one("#mainview .breach, #mainview .wallBreach, #mainview .warning")
        if breach_el is not None:
            breach_text = breach_el.get_text(" ", strip=True)
            if breach_text:
                self.isBreached = True
                self.breachInfo = breach_text
        elif self.level > 0 and self.hitPoints == 0:
            self.isBreached = True

"""Model for the Ikariam Chronos' Forge building (``view=chronosForge``)."""

from typing import TYPE_CHECKING, Any, Dict, Optional

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import (
    AjaxResponse,
    parse_float,
)
from ikabot.ikariam.buildings._base import (
    Building,
    tmpl_text,
)

if TYPE_CHECKING:
    from ikabot.ikariam.city import City
    from ikabot.ikariam.client import Client


class ChronosForge(Building):
    """Chronos' Forge view model with current and next-level construction time reductions."""

    effectPercent: Optional[float]
    timeReductionPercent: float
    nextLevelEffectPercent: Optional[float]
    nextLevelTimeReductionPercent: Optional[float]

    def __init__(
        self,
        client: Optional["Client"] = None,
        city: Optional["City"] = None,
        cityId: int = 0,
        position: int = 0,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a Chronos' Forge building model without making HTTP requests."""
        super().__init__(
            client=client,
            city=city,
            cityId=cityId,
            position=position,
            data=data,
        )
        if not self.buildingType:
            self.buildingType = "chronosForge"
        self._reset_fields()

    def _reset_fields(self) -> None:
        """Reset view-specific attributes before parsing a Chronos' Forge payload."""
        self.effectPercent = None
        self.timeReductionPercent = 0.0
        self.nextLevelEffectPercent = None
        self.nextLevelTimeReductionPercent = None

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        """Extract construction time reduction percentages for current and next levels."""
        self._reset_fields()

        eff_raw = tmpl_text(resp, "chronosForge .effectPercent")
        if not eff_raw:
            eff_el = soup.select_one("#mainview .effectPercent")
            eff_raw = eff_el.get_text(" ", strip=True) if eff_el is not None else ""
        self.effectPercent = parse_float(eff_raw)
        self.timeReductionPercent = (
            abs(self.effectPercent) if self.effectPercent is not None else 0.0
        )

        next_raw = tmpl_text(resp, "sidebar .sidebar_chronosForge .nextLevelEffect")
        if not next_raw:
            next_el = soup.select_one(".nextLevelEffect")
            next_raw = next_el.get_text(" ", strip=True) if next_el is not None else ""
        self.nextLevelEffectPercent = parse_float(next_raw)
        self.nextLevelTimeReductionPercent = (
            abs(self.nextLevelEffectPercent)
            if self.nextLevelEffectPercent is not None
            else None
        )

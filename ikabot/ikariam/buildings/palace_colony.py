"""Governor's Residence building model (``view=palaceColony``)."""

from typing import Any, Optional

from bs4 import BeautifulSoup

from ikabot.ikariam._parsing import AjaxResponse
from ikabot.ikariam.buildings._mixins import _GovernanceBuilding


class PalaceColony(_GovernanceBuilding):
    """Governor's Residence in a colony displaying empire towns and capital relocation."""

    buildingId = 17
    buildingType = "palaceColony"

    canRelocateCapital: bool
    relocateCapitalUrl: Optional[str]

    def _parse_body(self, soup: BeautifulSoup, resp: AjaxResponse) -> None:
        self._parse_empire_table(soup)
        move_box = soup.find(id="moveCapital")
        move_btn = move_box.select_one("a.button") if move_box is not None else None
        self.relocateCapitalUrl = (
            str(move_btn["href"]) if move_btn is not None and move_btn.get("href") else None
        )
        self.canRelocateCapital = self.relocateCapitalUrl is not None

    async def relocateCapital(self) -> Any:
        """Relocate the empire's capital to this colony."""
        ...

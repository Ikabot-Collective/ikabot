"""Depot building model (``view=dump``)."""

from typing import Any

from ikabot.ikariam.buildings._mixins import _StorageBuilding


class Dump(_StorageBuilding):
    """Depot building providing expanded resource storage capacity in the city."""

    buildingId = 29
    buildingType = "dump"

    async def activateSafeCapacityBonus(self) -> Any:
        """Activate the premium theft-security capacity bonus."""
        ...

    async def activateStorageCapacityBonus(self) -> Any:
        """Activate the premium total storage capacity bonus."""
        ...

"""Warehouse building model (``view=warehouse``)."""

from typing import Any

from ikabot.ikariam.buildings._mixins import _StorageBuilding


class Warehouse(_StorageBuilding):
    """Warehouse building storing and protecting city resources from plunder."""

    buildingId = 7
    buildingType = "warehouse"

    async def activateSafeCapacityBonus(self) -> Any:
        """Activate the premium theft-security capacity bonus."""
        ...

    async def activateStorageCapacityBonus(self) -> Any:
        """Activate the premium total storage capacity bonus."""
        ...

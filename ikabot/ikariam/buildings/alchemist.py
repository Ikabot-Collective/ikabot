"""Alchemist's Tower building model (``view=alchemist``)."""

from ikabot.ikariam.buildings._mixins import _ProductionBonusBuilding


class Alchemist(_ProductionBonusBuilding):
    """Alchemist's Tower building boosting sulphur production in the city."""

    buildingId = 22
    buildingType = "alchemist"
    resourceName = "Sulphur"

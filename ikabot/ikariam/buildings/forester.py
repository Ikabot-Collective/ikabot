"""Forester's House building model (``view=forester``)."""

from ikabot.ikariam.buildings._mixins import _ProductionBonusBuilding


class Forester(_ProductionBonusBuilding):
    """Forester's House building boosting wood production in the city."""

    buildingId = 18
    buildingType = "forester"
    resourceName = "Wood"

"""Glassblower building model (``view=glassblowing``)."""

from ikabot.ikariam.buildings._mixins import _ProductionBonusBuilding


class Glassblowing(_ProductionBonusBuilding):
    """Glassblower building boosting crystal glass production in the city."""

    buildingId = 20
    buildingType = "glassblowing"
    resourceName = "Crystal"

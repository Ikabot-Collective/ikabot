"""Stonemason building model (``view=stonemason``)."""

from ikabot.ikariam.buildings._mixins import _ProductionBonusBuilding


class Stonemason(_ProductionBonusBuilding):
    """Stonemason building boosting marble production in the city."""

    buildingId = 19
    buildingType = "stonemason"
    resourceName = "Marble"

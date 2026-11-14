"""Winery building model (``view=winegrower``)."""

from ikabot.ikariam.buildings._mixins import _ProductionBonusBuilding


class Winegrower(_ProductionBonusBuilding):
    """Winery building boosting wine production in the city."""

    buildingId = 21
    buildingType = "winegrower"
    resourceName = "Wine"

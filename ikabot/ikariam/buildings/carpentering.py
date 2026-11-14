"""Carpenter's Workshop building model (``view=carpentering``)."""

from ikabot.ikariam.buildings._mixins import _CostReductionBuilding


class Carpentering(_CostReductionBuilding):
    """Carpenter's Workshop reducing wood costs for buildings, units, and ships."""

    buildingId = 23
    buildingType = "carpentering"
    resourceName = "Wood"

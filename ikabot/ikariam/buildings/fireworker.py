"""Firework Test Area building model (``view=fireworker``)."""

from ikabot.ikariam.buildings._mixins import _CostReductionBuilding


class Fireworker(_CostReductionBuilding):
    """Firework Test Area reducing sulphur costs for buildings, units, and ships."""

    buildingId = 27
    buildingType = "fireworker"
    resourceName = "Sulphur"

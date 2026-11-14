"""Optician building model (``view=optician``)."""

from ikabot.ikariam.buildings._mixins import _CostReductionBuilding


class Optician(_CostReductionBuilding):
    """Optician reducing crystal glass costs for buildings, units, ships, experiments, and improvements."""

    buildingId = 25
    buildingType = "optician"
    resourceName = "Crystal"

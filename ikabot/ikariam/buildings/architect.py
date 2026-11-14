"""Architect's Office building model (``view=architect``)."""

from ikabot.ikariam.buildings._mixins import _CostReductionBuilding


class Architect(_CostReductionBuilding):
    """Architect's Office reducing marble costs for city buildings."""

    buildingId = 24
    buildingType = "architect"
    resourceName = "Marble"

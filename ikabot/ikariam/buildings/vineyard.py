"""Wine Press building model (``view=vineyard``)."""

from ikabot.ikariam.buildings._mixins import _CostReductionBuilding


class Vineyard(_CostReductionBuilding):
    """Wine Press reducing wine costs for buildings, units, and tavern consumption."""

    buildingId = 26
    buildingType = "vineyard"
    resourceName = "Wine"

"""Shipyard building model (``view=shipyard``)."""

from ikabot.ikariam.buildings._mixins import _RecruitmentBuilding


class Shipyard(_RecruitmentBuilding):
    """Shipyard building used to view and construct military warships."""

    buildingId = 5
    buildingType = "shipyard"

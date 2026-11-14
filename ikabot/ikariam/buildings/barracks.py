"""Barracks building model (``view=barracks``)."""

from ikabot.ikariam.buildings._mixins import _RecruitmentBuilding


class Barracks(_RecruitmentBuilding):
    """Barracks building used to view and recruit land military units."""

    buildingId = 6
    buildingType = "barracks"

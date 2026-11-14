

from ikabot.ikariam._parsing import parse_int


class AvatarScore:
    """Player score breakdown returned on island views."""

    userId: int
    placement: int
    buildingScore: int
    researchScore: int
    armyScore: int
    gold: int

    def __init__(self, data: dict) -> None:
        self.userId = parse_int(data["avatar_id"]) or 0
        self.placement = parse_int(data["place"]) or 0
        self.buildingScore = parse_int(data["building_score_main"]) or 0
        self.researchScore = parse_int(data["research_score_main"]) or 0
        self.armyScore = parse_int(data["army_score_main"]) or 0
        self.gold = parse_int(data["trader_score_secondary"]) or 0

        self.__avatar_score_data = data

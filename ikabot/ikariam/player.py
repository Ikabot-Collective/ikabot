

class AvatarScore():

    userId: int
    placement: int
    buildingScore: int
    researchScore: int
    armyScore: int
    gold: int

    def __init__(self, data: dict) -> None:
        
        self.userId = int(data['avatar_id'].replace(',','')) # all of these numbers have a comma (,) in them. Even the user id -.-
        self.placement = int(data['place'].replace(',',''))
        self.buildingScore = int(data['building_score_main'].replace(',',''))
        self.researchScore = int(data['research_score_main'].replace(',',''))
        self.armyScore = int(data['army_score_main'].replace(',',''))
        self.gold = int(data['trader_score_secondary'].replace(',',''))

        self.__avatar_score_data = data

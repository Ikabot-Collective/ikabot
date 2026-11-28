import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.consolidateResources import prepare_consolidateResources
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN_CITIES = (
    ["111", "222", "333"],
    {"111": {"name": "Alpha"}, "222": {"name": "Beta"}, "333": {"name": "Gamma"}},
)
LIMITS = [100000, -1, 50000, -1, -1]


@patch("ikabot.helpers.taskConfig.getIdsOfCities", return_value=OWN_CITIES)
class TestPrepareConsolidateResources(unittest.TestCase):
    def test_is_registered_for_the_cli(self, _mock_ids):
        self.assertIs(_TASK_REGISTRY["consolidateResources"].prepare, prepare_consolidateResources)

    def test_normalizes_ids_and_fills_in_the_defaults(self, _mock_ids):
        self.assertEqual(
            prepare_consolidateResources(
                MagicMock(), limits=LIMITS, sourceCityIds=[111, "222"], destinationCityId=333
            ),
            {
                "limits": LIMITS,
                "sourceCityIds": ["111", "222"],
                "destinationCityId": "333",
                "intervalInHours": 1,
                "shipType": 1,
            },
        )

    def test_drops_the_destination_and_repeated_sources(self, _mock_ids):
        config = prepare_consolidateResources(
            MagicMock(), limits=LIMITS, sourceCityIds=["111", "111", "333"], destinationCityId="333"
        )
        self.assertEqual(config["sourceCityIds"], ["111"])

    def test_needs_a_source_besides_the_destination(self, _mock_ids):
        with self.assertRaisesRegex(ValueError, "at least one city other than the destination"):
            prepare_consolidateResources(
                MagicMock(), limits=LIMITS, sourceCityIds=["333"], destinationCityId="333"
            )

    def test_needs_five_limits(self, _mock_ids):
        with self.assertRaisesRegex(ValueError, "limits must be a list of 5 amounts"):
            prepare_consolidateResources(
                MagicMock(), limits=[1, 2, 3], sourceCityIds=["111"], destinationCityId="333"
            )

    def test_rejects_a_city_of_another_player(self, _mock_ids):
        with self.assertRaisesRegex(ValueError, "sourceCityIds 999 is not one of your cities"):
            prepare_consolidateResources(
                MagicMock(), limits=LIMITS, sourceCityIds=["999"], destinationCityId="333"
            )

    def test_rejects_an_unknown_ship_type(self, _mock_ids):
        with self.assertRaisesRegex(ValueError, "shipType must be at most 3, got 4"):
            prepare_consolidateResources(
                MagicMock(), limits=LIMITS, sourceCityIds=["111"], destinationCityId="333", shipType=4
            )


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import MagicMock, patch

from ikabot.function.resourceTransportManager import do_it_unified, prepare_resourceTransportManager
from ikabot.helpers.decorators import _TASK_REGISTRY

OWN = (["111", "222", "333"], {"111": {"name": "Alpha"}, "222": {"name": "Beta"}, "333": {"name": "Gamma"}})
ISLAND = {"id": "4415", "x": 50, "y": 60, "cities": [{"type": "city", "id": 9000, "name": "Foreign"}, {"type": "empty"}]}
CONSOLIDATE = {"mode": "consolidate", "origin_cities": [111, "222"], "destination_city": 333, "send_mode": "keep",
               "resource_config": {"wood": 5000, "wine": 0}}


def patches(test, notifications=True):
    for target, kwargs in [
        ("ikabot.helpers.taskConfig.getIdsOfCities", {"return_value": OWN}),
        ("ikabot.function.resourceTransportManager.getIdsOfCities", {"return_value": OWN}),
        ("ikabot.function.sendResources.getIsland", {"return_value": ISLAND}),
        ("ikabot.function.resourceTransportManager.telegramDataIsValid", {"return_value": notifications}),
        ("ikabot.function.resourceTransportManager.discordDataIsValid", {"return_value": False}),
    ]:
        patcher = patch(target, **kwargs)
        patcher.start()
        test.addCleanup(patcher.stop)


class TestPrepareResourceTransportManager(unittest.TestCase):
    def setUp(self):
        patches(self)

    def test_is_registered_for_the_cli(self):
        self.assertIs(_TASK_REGISTRY["resourceTransportManager"].prepare, prepare_resourceTransportManager)

    def test_consolidate_to_your_city(self):
        config = prepare_resourceTransportManager(MagicMock(), **dict(CONSOLIDATE, interval_hours="6", notify="start"))
        self.assertEqual(config, {
            "mode": "consolidate", "interval_hours": 6, "useFreighters": False, "notify": "start",
            "origin_cities": ["111", "222"], "destination_city": "333", "send_mode": "keep",
            "resource_config": [5000, 0, None, None, None],
        })

    def test_the_destination_does_not_send_to_itself(self):
        config = prepare_resourceTransportManager(MagicMock(), **dict(CONSOLIDATE, origin_cities=[111, 333, 111]))
        self.assertEqual(config["origin_cities"], ["111"])
        with self.assertRaisesRegex(ValueError, "origin_cities has no city other than destination_city"):
            prepare_resourceTransportManager(MagicMock(), **dict(CONSOLIDATE, origin_cities=[333]))

    def test_consolidate_to_another_players_city_needs_its_island(self):
        foreign = dict(CONSOLIDATE, destination_city=9000)
        with self.assertRaisesRegex(ValueError, "island is needed when destination_city is not your city"):
            prepare_resourceTransportManager(MagicMock(), **foreign)
        self.assertEqual(prepare_resourceTransportManager(MagicMock(), **dict(foreign, island="50:60"))["island"], "4415")
        with self.assertRaisesRegex(ValueError, "destination_city 9001 is not on island 50:60"):
            prepare_resourceTransportManager(MagicMock(), **dict(foreign, destination_city=9001, island=4415))

    def test_distribute(self):
        config = prepare_resourceTransportManager(
            MagicMock(), mode="Distribute", origin_city=111, destination_cities=[222, 111, "333"],
            resource_config=[1000, None, 0, 0, 0], useFreighters="y",
        )
        self.assertEqual(config, {
            "mode": "distribute", "interval_hours": 0, "useFreighters": True, "notify": "none",
            "origin_city": "111", "destination_cities": ["222", "333"], "resource_config": [1000, 0, 0, 0, 0],
        })

    def test_rejects_bad_values(self):
        bad = [
            (dict(CONSOLIDATE, mode="both"), 'mode must be "consolidate"'),
            (dict(CONSOLIDATE, send_mode="some"), 'send_mode must be "keep"'),
            (dict(CONSOLIDATE, notify="always"), 'notify must be "none", "start" or "all"'),
            (dict(CONSOLIDATE, interval_hours=-1), "interval_hours must be at least 0"),
            (dict(CONSOLIDATE, origin_cities=[999]), "origin_cities\\[0\\] 999 is not one of your cities"),
            (dict(CONSOLIDATE, origin_cities=[]), "origin_cities must be a list"),
            (dict(CONSOLIDATE, resource_config={"gold": 5}), "unknown resources \\['gold'\\]"),
            (dict(CONSOLIDATE, resource_config=[None] * 5), "resource_config sends nothing"),
            (dict(CONSOLIDATE, send_mode="send", resource_config=[0, None, 0, 0, 0]), "resource_config sends nothing"),
            ({"mode": "distribute", "origin_city": 111, "destination_cities": [111], "resource_config": [5, 0, 0, 0, 0]},
             "destination_cities has no city other than origin_city"),
            ({"mode": "distribute", "origin_city": 111, "destination_cities": [222], "resource_config": [0, 0, 0, 0, 0]},
             "resource_config sends nothing"),
            ({"mode": "distribute", "destination_cities": [222], "resource_config": [5, 0, 0, 0, 0]}, "origin_city is needed"),
        ]
        for config, error in bad:
            with self.subTest(error):
                with self.assertRaisesRegex(ValueError, error):
                    prepare_resourceTransportManager(MagicMock(), **config)

    def test_notifications_need_a_bot(self):
        with patch("ikabot.function.resourceTransportManager.telegramDataIsValid", return_value=False):
            with self.assertRaisesRegex(ValueError, 'notify "all" needs Telegram or Discord'):
                prepare_resourceTransportManager(MagicMock(), **dict(CONSOLIDATE, notify="all"))
            self.assertEqual(prepare_resourceTransportManager(MagicMock(), **CONSOLIDATE)["notify"], "none")

    def test_accepts_a_config_saved_by_an_older_menu(self):
        alpha = {"id": "111", "name": "Alpha", "position": ["lots", "of", "data"]}
        foreign = {"id": "9000", "name": "Foreign", "isOwnCity": False}
        config = prepare_resourceTransportManager(
            MagicMock(), mode="consolidate", info="\nAuto-send...\n", origin_cities=[alpha], destination_city=foreign,
            island=ISLAND, interval_hours=2, resource_config=[0, None, None, None, None], useFreighters=False,
            send_mode=1, telegram_enabled=None, notify_on_start=True,
        )
        self.assertEqual(config, {
            "mode": "consolidate", "interval_hours": 2, "useFreighters": False, "notify": "start",
            "origin_cities": ["111"], "destination_city": "9000", "send_mode": "keep",
            "resource_config": [0, None, None, None, None], "island": "4415",
        })


@patch("ikabot.function.resourceTransportManager.setInfoSignal")
@patch("ikabot.function.resourceTransportManager.do_it_distribute")
@patch("ikabot.function.resourceTransportManager.do_it")
@patch("ikabot.function.resourceTransportManager.getIsland", return_value=ISLAND)
@patch("ikabot.function.resourceTransportManager.getCity",
       side_effect=lambda html: {"id": html.split("=")[-1], "name": "City " + html.split("=")[-1], "islandId": "77"})
@patch("ikabot.function.resourceTransportManager.getIdsOfCities", return_value=OWN)
class TestResourceTransportTask(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.session.get.side_effect = lambda url="": url

    def test_consolidate_reads_the_cities(self, _ids, _city, _island, mock_do_it, _distribute, _info):
        do_it_unified.__wrapped__(self.session, mode="consolidate", origin_cities=["111", "222"], destination_city="333",
                                  interval_hours=2, resource_config=[5000, 0, None, None, None], send_mode="send", notify="start")
        session, origins, destination, island, hours, amounts, freighters, send_mode, every, on_start = mock_do_it.call_args.args
        self.assertEqual([c["id"] for c in origins], ["111", "222"])
        self.assertEqual((destination["id"], destination["isOwnCity"]), ("333", True))
        self.assertEqual((hours, amounts, freighters, send_mode, every, on_start), (2, [5000, 0, None, None, None], False, 2, None, True))

    def test_another_players_city_is_not_read_as_yours(self, mock_ids, mock_city, _island, mock_do_it, _distribute, _info):
        do_it_unified.__wrapped__(self.session, mode="consolidate", origin_cities=["111"], destination_city="9000",
                                  island="4415", resource_config=[0, None, None, None, None], send_mode="keep", notify="all")
        destination = mock_do_it.call_args.args[2]
        self.assertEqual(destination, {"id": "9000", "name": "Foreign", "islandId": "4415", "isOwnCity": False})
        self.assertEqual(mock_do_it.call_args.args[7:], (1, True, True))

    def test_distribute(self, _ids, _city, _island, _do_it, mock_distribute, _info):
        do_it_unified.__wrapped__(self.session, mode="distribute", origin_city="111", destination_cities=["222", "333"],
                                  resource_config=[1000, 0, 0, 0, 0], useFreighters=True)
        session, origin, destinations, hours, amounts, freighters, every, on_start = mock_distribute.call_args.args
        self.assertEqual((origin["id"], [c["id"] for c in destinations]), ("111", ["222", "333"]))
        self.assertEqual((hours, amounts, freighters, every, on_start), (0, [1000, 0, 0, 0, 0], True, None, False))


if __name__ == "__main__":
    unittest.main()

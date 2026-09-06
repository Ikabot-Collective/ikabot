import unittest
from unittest.mock import Mock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.function.autoPirate import getPirateFortressPoints

# the fortress reports its state in the params of the updateTemplateData object, this is
# the shape of that response
FORTRESS_RESPONSE = (
    '[[["updateTemplateData",{"filepath":"//gf2.geo.gfsrv.net/cdna0/7254428.js",'
    '"params":"{\\"serverTime\\":1684007856,\\"view\\":\\"pirateFortress\\",'
    '\\"position\\":17,\\"buildingLevel\\":15,\\"capturePoints\\":\\"80169\\",'
    '\\"crewPoints\\":\\"18407\\",\\"basicCrewPoints\\":36,\\"bonusCrewPoints\\":1400,'
    '\\"completeCrewPoints\\":19843,\\"crewConversionFactor\\":10}"}]]]'
)


class TestGetPirateFortressPoints(unittest.TestCase):
    """Test reading the capture points and the crew strength of the account"""

    def setUp(self):
        """Set up test fixtures"""
        self.session = Mock()
        self.session.post.return_value = FORTRESS_RESPONSE

    def test_points_are_read_from_the_fortress(self):
        """Both numbers come from the same response"""
        self.assertEqual(getPirateFortressPoints(self.session, 12345), (80169, 19843))

    def test_crew_strength_includes_the_basic_and_the_bonus_crew(self):
        """crewPoints is only the crew converted from capture points, the strength the
        game shows is completeCrewPoints (18407 + 36 + 1400)"""
        (__, crew_strength) = getPirateFortressPoints(self.session, 12345)

        self.assertEqual(crew_strength, 19843)

    def test_crew_strength_is_read_with_no_capture_points(self):
        """A player who never converted has crewPoints 0 but still has crew strength"""
        self.session.post.return_value = FORTRESS_RESPONSE.replace(
            '\\"crewPoints\\":\\"18407\\"', '\\"crewPoints\\":\\"0\\"'
        ).replace('\\"completeCrewPoints\\":19843', '\\"completeCrewPoints\\":128')

        self.assertEqual(getPirateFortressPoints(self.session, 12345), (80169, 128))

    def test_the_fortress_is_asked_for_the_given_city(self):
        """Any city with a fortress reports the same points, the fortress is on position 17"""
        getPirateFortressPoints(self.session, 12345)

        params = self.session.post.call_args.kwargs["params"]
        self.assertEqual(params["cityId"], 12345)
        self.assertEqual(params["currentCityId"], 12345)
        self.assertEqual(params["position"], 17)
        self.assertEqual(params["view"], "pirateFortress")

    def test_missing_points_are_reported_as_none(self):
        """A response without the points must not be shown as zero"""
        self.session.post.return_value = '[[["updateTemplateData",{"params":"{}"}]]]'

        self.assertIsNone(getPirateFortressPoints(self.session, 12345))


if __name__ == '__main__':
    unittest.main()

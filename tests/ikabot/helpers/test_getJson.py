import unittest
from unittest.mock import Mock
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from ikabot.helpers.getJson import getInventory, getInventoryItem


VALID_INVENTORY_HTML = (
    'some prefix "inventory": [{"itemId": 2201, "count": "1,500"}, '
    '{"itemId": 300, "count": "2"}] some suffix'
)


class TestGetInventory(unittest.TestCase):

    def _session(self, html):
        session = Mock()
        session.get.return_value = html
        return session

    def test_valid_inventory_is_parsed(self):
        inventory = getInventory(self._session(VALID_INVENTORY_HTML))
        self.assertEqual(len(inventory), 2)
        self.assertEqual(inventory[0]["itemId"], 2201)

    def test_missing_inventory_returns_empty_list(self):
        """A response without inventory JSON must not return None (used to
        crash getInventoryItem with TypeError)"""
        inventory = getInventory(self._session('<html>error page</html>'))
        self.assertEqual(inventory, [])

    def test_get_item_found(self):
        item = getInventoryItem(self._session(VALID_INVENTORY_HTML), 2201)
        self.assertEqual(item["count"], "1,500")

    def test_get_item_not_found(self):
        item = getInventoryItem(self._session(VALID_INVENTORY_HTML), 9999)
        self.assertIsNone(item)

    def test_get_item_with_unparseable_inventory(self):
        """Must return None, not raise TypeError"""
        item = getInventoryItem(self._session('<html>error page</html>'), 2201)
        self.assertIsNone(item)


if __name__ == '__main__':
    unittest.main()

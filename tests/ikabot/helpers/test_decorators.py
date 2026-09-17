import multiprocessing
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from ikabot.helpers.decorators import (
    _TASK_REGISTRY,
    configurator,
    task,
)


class TestDecorators(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.session.logout = MagicMock()
        self.event = multiprocessing.Event()

    def test_config_only_module_returns_none(self):
        @configurator
        def dummy_config_only(session, event, stdin_fd, predetermined_input):
            return None

        # Call configurator
        dummy_config_only(self.session, self.event, None, [])
        self.assertTrue(self.event.is_set())

    @patch("ikabot.helpers.decorators.set_child_mode")
    def test_config_and_task_handoff(self, mock_set_child_mode):
        executed_task_kwargs = {}

        @task("dummy_feature")
        def dummy_task(session, city_id, amount):
            executed_task_kwargs["session"] = session
            executed_task_kwargs["city_id"] = city_id
            executed_task_kwargs["amount"] = amount

        @configurator
        def dummy_feature(session, event, stdin_fd, predetermined_input):
            return {
                "session": session,
                "city_id": 42,
                "amount": 1000,
            }

        dummy_feature(self.session, self.event, None, [])

        # Verify child mode was set and event was signaled
        mock_set_child_mode.assert_called_once_with(self.session)
        self.assertTrue(self.event.is_set())

        # Verify task received exact kwargs
        self.assertEqual(executed_task_kwargs["session"], self.session)
        self.assertEqual(executed_task_kwargs["city_id"], 42)
        self.assertEqual(executed_task_kwargs["amount"], 1000)

        # Verify session.logout() was automatically called
        self.session.logout.assert_called_once()

    @patch("ikabot.helpers.decorators.set_child_mode")
    def test_blocking_configurator(self, mock_set_child_mode):
        order_of_execution = []

        @task("blocking_feature")
        def blocking_task(session):
            order_of_execution.append("task_executed")

        @configurator(blocking=True)
        def blocking_feature(session, event, stdin_fd, predetermined_input):
            return {"session": session}

        blocking_feature(self.session, self.event, None, [])

        # In blocking mode, child mode is not set and task finishes before event.set()
        self.assertEqual(order_of_execution, ["task_executed"])
        self.assertTrue(self.event.is_set())
        mock_set_child_mode.assert_not_called()
        self.session.logout.assert_called_once()

    @patch("ikabot.helpers.decorators._send_error")
    def test_task_error_handling_and_logout(self, mock_send_error):
        @task("failing_feature")
        def failing_task(session):
            raise ValueError("Something went wrong")

        @configurator
        def failing_feature(session, event, stdin_fd, predetermined_input):
            return {"session": session}

        with self.assertRaises(ValueError):
            failing_feature(self.session, self.event, None, [])

        # Error notification called and logout called even on exception
        mock_send_error.assert_called_once()
        self.session.logout.assert_called_once()

    def test_keyboard_interrupt_in_configurator(self):
        @configurator
        def interrupted_feature(session, event, stdin_fd, predetermined_input):
            raise KeyboardInterrupt()

        interrupted_feature(self.session, self.event, None, [])
        self.assertTrue(self.event.is_set())

#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Decorators for separating interactive configuration from background task execution.

Every ikabot function module has an interactive configuration phase (the ``@configurator``)
and optionally a long-running background phase (the ``@task``).

Usage
-----

**Config-only module** (no background work)::

    @configurator
    def viewArmy(session, event, stdin_fd, predetermined_input):
        # ... interactive display ...
        return None  # signals "nothing to run in background"

**Config + task module**::

    @configurator
    def alertAttacks(session, event, stdin_fd, predetermined_input):
        # ... interactive prompts ...
        minutes = read(msg="How often? ", min=3, default=20)
        return {"session": session, "minutes": minutes}

    @task("alertAttacks")
    def do_it(session, minutes):
        # ALL state needed to run is in the parameters.
        # This function can be invoked independently.
        while True:
            ...

**Blocking configurator** (keeps CLI blocked until task finishes)::

    @configurator(blocking=True)
    def dumpWorld(session, event, stdin_fd, predetermined_input):
        ...
        return {"session": session, "waiting_time": wt, ...}

    @task("dumpWorld")
    def do_it(session, waiting_time, ...):
        ...
"""

import functools
import os
import sys
import traceback

import ikabot.config as config
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.signals import setInfoSignal

# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------
# Maps configurator function name -> task wrapper function.
# Populated by the @task decorator at import time.
_TASK_REGISTRY = {}


def _send_error(session, info, exc_text):
    """Best-effort error notification via Telegram/Discord bot."""
    try:
        from ikabot.helpers.botComm import sendToBot
        msg = "Error in:\n{}\nCause:\n{}".format(info, exc_text)
        sendToBot(session, msg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# @task decorator
# ---------------------------------------------------------------------------

def task(configurator_name):
    """Register a background task function for a given configurator.

    Parameters
    ----------
    configurator_name : str
        The ``__name__`` of the ``@configurator``-decorated function this task
        belongs to.  This is used as the lookup key so the configurator can
        find and invoke its task automatically.

    The decorated function **must** accept all its runtime state as explicit
    keyword parameters (no reliance on module-level globals for configuration).
    The configurator returns a dict whose keys match the task's parameter names.
    The first positional argument is conventionally ``session``.

    The decorator automatically:
    * calls ``session.logout()`` in a ``finally`` block
    * catches unhandled exceptions and forwards them to the user via
      ``sendToBot``
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Determine session: first positional arg, or keyword 'session'
            session = kwargs.get("session") or (args[0] if args else None)
            try:
                return func(*args, **kwargs)
            except Exception:
                _send_error(session, func.__name__, traceback.format_exc())
                raise
            finally:
                if session is not None and hasattr(session, "logout"):
                    try:
                        session.logout()
                    except Exception:
                        pass

        # Register in the global task registry
        _TASK_REGISTRY[configurator_name] = wrapper
        # Keep a reference to the original unwrapped function for direct use
        wrapper.__wrapped__ = func
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# @configurator decorator
# ---------------------------------------------------------------------------

def configurator(_func=None, *, blocking=False):
    """Mark a function as a module's interactive configuration entry point.

    Parameters
    ----------
    blocking : bool, optional
        If ``True``, the CLI menu stays blocked until the task finishes
        (used by modules like ``dumpWorld`` that show a live progress UI).
        Default is ``False`` (the normal case where the CLI is released
        immediately after configuration so the user can queue more tasks).

    The decorated function must have the standard ikabot entry signature::

        def func(session, event, stdin_fd, predetermined_input):

    It should **return** one of:

    * ``None`` — config-only module, no background task to run.
    * a ``dict`` — keyword arguments to pass to the matching ``@task``
      function.  The dict keys must match the task function's parameter
      names exactly.  The dict **must** include ``"session"`` so the task
      has access to the game session.

    The decorator handles:
    * ``sys.stdin = os.fdopen(stdin_fd)``
    * ``config.predetermined_input = predetermined_input``
    * ``set_child_mode(session)`` + ``event.set()`` handoff (unless blocking)
    * ``event.set()`` for config-only modules
    * ``KeyboardInterrupt`` handling
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(session, event, stdin_fd, predetermined_input):
            # Set up stdin and predetermined input for the child process
            try:
                if stdin_fd is not None:
                    sys.stdin = os.fdopen(stdin_fd)
            except Exception:
                pass
            config.predetermined_input = predetermined_input

            try:
                result = func(session, event, stdin_fd, predetermined_input)
            except KeyboardInterrupt:
                event.set()
                return
            except Exception:
                event.set()
                raise

            if result is None:
                # Config-only module — signal completion and exit
                event.set()
                return

            # Config + task module — look up the registered task
            task_func = _TASK_REGISTRY.get(func.__name__)
            if task_func is None:
                # No @task registered for this configurator — treat as
                # config-only (this is a programming error, but fail safe)
                event.set()
                return

            if blocking:
                # Blocking mode: run the task, THEN release the CLI
                try:
                    task_func(**result)
                finally:
                    event.set()
            else:
                # Normal mode: release the CLI, then run the task in background
                set_child_mode(session)
                event.set()
                task_func(**result)

        # Preserve metadata for introspection
        wrapper._is_configurator = True
        wrapper._blocking = blocking
        return wrapper

    # Support both @configurator and @configurator(blocking=True) syntax
    if _func is not None:
        # Called as @configurator without parentheses
        return decorator(_func)
    # Called as @configurator(...) with keyword arguments
    return decorator

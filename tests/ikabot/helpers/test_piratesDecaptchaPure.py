"""Numerical and behavioural checks for the pure-Python pirate decaptcha.

The solver ships Winograd-domain weights to its worker processes as
array.array('d') buffers and rebuilds the per-output-channel rows as
memoryview slices, instead of pickling nested lists of Python floats. That
keeps a worker at ~44 MB instead of ~152 MB, which is what makes running
several accounts at once survivable -- but it changes the *type* the inner
dot product consumes, so it has to be proven not to change the *values*.

    python -m pytest tests/ikabot/helpers/test_piratesDecaptchaPure.py
"""
import os
import random

import pytest

from ikabot.helpers import piratesDecaptchaPure as P

IMG_DIR = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "api", "img")

# (C_in, C_out, H, W) for every 3x3 convolution that takes the Winograd path.
# rb4 has H=6, which is not a multiple of 4, so it exercises the ceil-tiling
# and the discarding of the overflow rows.
GEOMETRIES = [
    (32, 32, 48, 256),   # rb1.conv2
    (32, 64, 24, 128),   # rb2.conv1
    (64, 64, 24, 128),   # rb2.conv2
    (64, 128, 12, 64),   # rb3.conv1
    (128, 128, 12, 64),  # rb3.conv2
    (128, 256, 6, 64),   # rb4.conv1
    (256, 256, 6, 64),   # rb4.conv2
]

KNOWN_CAPTCHAS = [("pirate1.png", "QKB24JC"), ("pirate2.png", "DEVL5KA")]


def _as_worker_sees_it(U36, C_out):
    """Rebuild the weight rows exactly as the pool initializer does."""
    planes, C_in = P._pack_wino({"probe::wino": U36})["probe::wino"]
    return [[memoryview(plane)[oc * C_in:(oc + 1) * C_in] for oc in range(C_out)]
            for plane in planes]


@pytest.mark.parametrize("C_in,C_out,H,W", GEOMETRIES)
def test_packed_weights_are_bit_identical_to_nested_lists(C_in, C_out, H, W):
    """The memoryview rows a worker uses must give the same floats, bit for
    bit, as the nested lists the parent uses when it solves serially."""
    rng = random.Random(1234)
    # A narrow channel slice keeps the direct-convolution reference quick; the
    # tiling depends on H and W, not on the channel count.
    ci, co = min(C_in, 4), min(C_out, 4)
    w = [rng.uniform(-0.5, 0.5) for _ in range(co * ci * 9)]
    b = [rng.uniform(-0.2, 0.2) for _ in range(co)]
    x = [rng.uniform(-1.0, 1.0) for _ in range(ci * H * W)]

    U36 = P._wino_transform_weights(w, co, ci)

    reference = P.conv2d_3x3_pad1(x, w, b, ci, co, H, W)
    nested = P.conv2d_3x3_wino(x, U36, b, ci, co, H, W)
    packed = P.conv2d_3x3_wino(x, _as_worker_sees_it(U36, co), b, ci, co, H, W)

    assert packed == nested, "packing the weights changed the result"

    # Winograd is algebraically exact; the gap to a direct convolution is pure
    # floating-point reassociation.
    worst = max(abs(a - c) for a, c in zip(reference, nested))
    assert worst < 1e-9, "Winograd diverged from the direct convolution: %.3e" % worst


@pytest.mark.parametrize("name,expected", KNOWN_CAPTCHAS)
def test_known_captcha_is_decoded(name, expected):
    with open(os.path.join(IMG_DIR, name), "rb") as f:
        assert P.get_captcha_string(f.read()) == expected


def test_parallel_forward_matches_serial():
    """A pooled solve and a single-process solve must produce identical
    logits: splitting the work into stripes is a scheduling decision, not a
    numerical one."""
    if not P.USE_MULTIPROCESSING:
        pytest.skip("multiprocessing disabled by configuration")

    weights = P.get_cached_weights()
    with open(os.path.join(IMG_DIR, "pirate1.png"), "rb") as f:
        x = P.preprocess_image(f.read())

    P._drop_pool()
    serial = P.forward(x, weights)

    try:
        workers = P._ensure_pool(weights)
        if workers < 2:
            pytest.skip("machine had no spare cores or RAM for a pool")
        parallel = P.forward(x, weights)
    finally:
        P._drop_pool()

    worst = max(abs(a - c)
                for srow, prow in zip(serial, parallel)
                for a, c in zip(srow, prow))
    assert worst == 0.0, "parallel forward drifted from serial by %.3e" % worst


def test_pool_is_not_created_at_load_time():
    """Captchas are rare; a pool warmed at load time would sit idle holding
    the weights of every worker for the lifetime of the task process."""
    P._drop_pool()
    P.load_weights()
    assert P._SPAWN_POOL is None


def test_idle_release_frees_weights_without_another_solve(monkeypatch):
    """An account that saw one captcha and then went quiet must not keep the
    weights resident. The cleanup cannot wait for the next solve, because
    there may never be one."""
    import time

    monkeypatch.setattr(P, "_IDLE_TIMEOUT", 0.2)
    P._WEIGHTS_CACHE = {"sentinel": True}
    P._LAST_SOLVE = time.time()
    P._SOLVING = False
    P._schedule_idle_release()

    deadline = time.time() + 5.0
    while time.time() < deadline and P._WEIGHTS_CACHE is not None:
        time.sleep(0.1)
    assert P._WEIGHTS_CACHE is None


def test_worker_budget_is_released_when_seats_are_dropped():
    """Seats are held by OS file locks so a killed task cannot leak budget."""
    if not P.USE_MULTIPROCESSING:
        pytest.skip("multiprocessing disabled by configuration")
    P._init_mp()
    P._release_seats()
    before = P._seated()
    assert P._claim_seat() is True
    assert P._seated() == before + 1
    P._release_seats()
    assert P._seated() == before

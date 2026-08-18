#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import json
import math
import os
import struct
import zlib
from pathlib import Path
from operator import mul

try:
    from ikabot.config import USE_MULTIPROCESSING_DECAPTCHA
    USE_MULTIPROCESSING = bool(USE_MULTIPROCESSING_DECAPTCHA)
except Exception:
    USE_MULTIPROCESSING = True

try:
    from math import sumprod as _dot
except ImportError:
    def _dot(a, b, _sum=sum, _map=map, _mul=mul):
        return _sum(_map(_mul, a, b))

CHARSET = "abcdefghjklmnpqrstuvwxy23457"
BLANK = 0
NUM_CLASSES = len(CHARSET) + 1  # 29
IDX_TO_CHAR = {i + 1: c for i, c in enumerate(CHARSET)}

IMG_H = 48
IMG_W = 256

_MP_CTX = None
_MP_CORES = 1
_MP_FORK = False
_MP_INITIALIZED = False
_SPAWN_POOL = None
_SPAWN_WINO = None
_SPAWN_HAS_WINO = False
_MP_MIN_OPS = 1_000_000

_WEIGHTS_CACHE = None


def _init_spawn_wino(wino):
    global _SPAWN_WINO
    _SPAWN_WINO = wino


def _get_persistent_pool(wino=None):
    global _SPAWN_POOL, _SPAWN_HAS_WINO
    if not USE_MULTIPROCESSING:
        return None
    if _SPAWN_POOL is not None and wino is not None and not _SPAWN_HAS_WINO:
        _SPAWN_POOL.terminate()
        _SPAWN_POOL.join()
        _SPAWN_POOL = None
    if _SPAWN_POOL is None:
        if wino is not None:
            _SPAWN_POOL = _MP_CTX.Pool(_MP_CORES, initializer=_init_spawn_wino, initargs=(wino,))
            _SPAWN_HAS_WINO = True
        else:
            _SPAWN_POOL = _MP_CTX.Pool(_MP_CORES)
        import atexit

        def _cleanup():
            if _SPAWN_POOL is not None:
                _SPAWN_POOL.terminate()
                _SPAWN_POOL.join()
        atexit.register(_cleanup)
    return _SPAWN_POOL


def _warm_spawn_pool(weights):
    if not USE_MULTIPROCESSING:
        return
    _init_mp()
    if _MP_CTX is None:
        return
    wino = {k: v for k, v in weights.items() if k.endswith("::wino")}
    _get_persistent_pool(wino)


def _physical_cores(logical):
    try:
        import glob
        groups = set()
        for path in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/topology/thread_siblings_list"):
            with open(path) as f:
                groups.add(f.read().strip())
        if groups:
            return len(groups)
    except Exception:
        pass

    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        need = ctypes.c_ulong(0)
        kernel32.GetLogicalProcessorInformation(None, ctypes.byref(need))
        buf = ctypes.create_string_buffer(need.value)
        if kernel32.GetLogicalProcessorInformation(buf, ctypes.byref(need)):
            ptr = ctypes.sizeof(ctypes.c_void_p)
            stride = ptr + 8 + 16
            n = sum(1 for off in range(0, need.value, stride)
                    if struct.unpack_from("<I", buf, off + ptr)[0] == 0)
            if n:
                return n
    except Exception:
        pass

    return max(1, logical // 2) if logical >= 8 else logical


def _init_mp():
    global _MP_CTX, _MP_CORES, _MP_FORK, _MP_INITIALIZED
    if not USE_MULTIPROCESSING or _MP_INITIALIZED:
        return
    _MP_INITIALIZED = True
    cores = os.cpu_count() or 1
    if cores <= 1:
        return
    import multiprocessing as mp
    try:
        _MP_CTX = mp.get_context("fork")
        _MP_FORK = True
    except ValueError:
        _MP_CTX = mp.get_context()
        _MP_FORK = False
    _MP_CORES = max(2, _physical_cores(cores))


def _wino_transform_weights(w, C_out, C_in):
    U = [[] for _ in range(36)]
    apps = [u.append for u in U]
    c6 = 1.0 / 6.0
    c24 = 1.0 / 24.0
    idx = 0
    for _ in range(C_out * C_in):
        g0 = w[idx];     g1 = w[idx + 1]; g2 = w[idx + 2]
        g3 = w[idx + 3]; g4 = w[idx + 4]; g5 = w[idx + 5]
        g6 = w[idx + 6]; g7 = w[idx + 7]; g8 = w[idx + 8]
        idx += 9
        rows = (
            (0.25 * g0, 0.25 * g1, 0.25 * g2),
            (-(g0 + g3 + g6) * c6, -(g1 + g4 + g7) * c6, -(g2 + g5 + g8) * c6),
            ((-g0 + g3 - g6) * c6, (-g1 + g4 - g7) * c6, (-g2 + g5 - g8) * c6),
            ((g0 + 2.0 * g3 + 4.0 * g6) * c24, (g1 + 2.0 * g4 + 4.0 * g7) * c24, (g2 + 2.0 * g5 + 4.0 * g8) * c24),
            ((g0 - 2.0 * g3 + 4.0 * g6) * c24, (g1 - 2.0 * g4 + 4.0 * g7) * c24, (g2 - 2.0 * g5 + 4.0 * g8) * c24),
            (g6, g7, g8),
        )
        p = 0
        for (t0, t1, t2) in rows:
            apps[p](0.25 * t0)
            apps[p + 1](-(t0 + t1 + t2) * c6)
            apps[p + 2]((-t0 + t1 - t2) * c6)
            apps[p + 3]((t0 + 2.0 * t1 + 4.0 * t2) * c24)
            apps[p + 4]((t0 - 2.0 * t1 + 4.0 * t2) * c24)
            apps[p + 5](t2)
            p += 6
    return [[Up[oc * C_in: (oc + 1) * C_in] for oc in range(C_out)] for Up in U]


def _find_weights_file():
    candidates = [
        Path(__file__).resolve().parents[2] / "assets" / "local_purepython_decaptcha_weights.bin",
        Path(__file__).resolve().parents[1] / "assets" / "local_purepython_decaptcha_weights.bin",
        Path(__file__).resolve().parent / "assets" / "local_purepython_decaptcha_weights.bin",
        Path(__file__).resolve().parent / "local_purepython_decaptcha_weights.bin",
        Path("assets/local_purepython_decaptcha_weights.bin"),
        Path("local_purepython_decaptcha_weights.bin"),
    ]
    for p in candidates:
        if p.is_file():
            return p
    return candidates[0]


def load_weights(blob_path=None) -> dict:
    if blob_path is None:
        blob_path = _find_weights_file()
    else:
        blob_path = Path(blob_path)

    if not blob_path.is_file():
        raise FileNotFoundError(f"Pure-Python decaptcha weights binary not found at '{blob_path}'.")

    weights_json = """[
  {"name": "rb1.conv1.weight", "offset": 0, "shape": [32, 3, 3, 3], "n": 864},
  {"name": "rb1.conv1.bias", "offset": 3456, "shape": [32], "n": 32},
  {"name": "rb1.conv2.weight", "offset": 3584, "shape": [32, 32, 3, 3], "n": 9216},
  {"name": "rb1.conv2.bias", "offset": 40448, "shape": [32], "n": 32},
  {"name": "rb1.skip.weight", "offset": 40576, "shape": [32, 3, 1, 1], "n": 96},
  {"name": "rb1.skip.bias", "offset": 40960, "shape": [32], "n": 32},
  {"name": "rb1.se.fc1.weight", "offset": 41088, "shape": [8, 32], "n": 256},
  {"name": "rb1.se.fc1.bias", "offset": 42112, "shape": [8], "n": 8},
  {"name": "rb1.se.fc2.weight", "offset": 42144, "shape": [32, 8], "n": 256},
  {"name": "rb1.se.fc2.bias", "offset": 43168, "shape": [32], "n": 32},
  {"name": "rb2.conv1.weight", "offset": 43296, "shape": [64, 32, 3, 3], "n": 18432},
  {"name": "rb2.conv1.bias", "offset": 117024, "shape": [64], "n": 64},
  {"name": "rb2.conv2.weight", "offset": 117280, "shape": [64, 64, 3, 3], "n": 36864},
  {"name": "rb2.conv2.bias", "offset": 264736, "shape": [64], "n": 64},
  {"name": "rb2.skip.weight", "offset": 264992, "shape": [64, 32, 1, 1], "n": 2048},
  {"name": "rb2.skip.bias", "offset": 273184, "shape": [64], "n": 64},
  {"name": "rb2.se.fc1.weight", "offset": 273440, "shape": [16, 64], "n": 1024},
  {"name": "rb2.se.fc1.bias", "offset": 277536, "shape": [16], "n": 16},
  {"name": "rb2.se.fc2.weight", "offset": 277600, "shape": [64, 16], "n": 1024},
  {"name": "rb2.se.fc2.bias", "offset": 281696, "shape": [64], "n": 64},
  {"name": "rb3.conv1.weight", "offset": 281952, "shape": [128, 64, 3, 3], "n": 73728},
  {"name": "rb3.conv1.bias", "offset": 576864, "shape": [128], "n": 128},
  {"name": "rb3.conv2.weight", "offset": 577376, "shape": [128, 128, 3, 3], "n": 147456},
  {"name": "rb3.conv2.bias", "offset": 1167200, "shape": [128], "n": 128},
  {"name": "rb3.skip.weight", "offset": 1167712, "shape": [128, 64, 1, 1], "n": 8192},
  {"name": "rb3.skip.bias", "offset": 1200480, "shape": [128], "n": 128},
  {"name": "rb3.se.fc1.weight", "offset": 1200992, "shape": [32, 128], "n": 4096},
  {"name": "rb3.se.fc1.bias", "offset": 1217376, "shape": [32], "n": 32},
  {"name": "rb3.se.fc2.weight", "offset": 1217504, "shape": [128, 32], "n": 4096},
  {"name": "rb3.se.fc2.bias", "offset": 1233888, "shape": [128], "n": 128},
  {"name": "rb4.conv1.weight", "offset": 1234400, "shape": [256, 128, 3, 3], "n": 294912},
  {"name": "rb4.conv1.bias", "offset": 2414048, "shape": [256], "n": 256},
  {"name": "rb4.conv2.weight", "offset": 2415072, "shape": [256, 256, 3, 3], "n": 589824},
  {"name": "rb4.conv2.bias", "offset": 4774368, "shape": [256], "n": 256},
  {"name": "rb4.skip.weight", "offset": 4775392, "shape": [256, 128, 1, 1], "n": 32768},
  {"name": "rb4.skip.bias", "offset": 4906464, "shape": [256], "n": 256},
  {"name": "rb4.se.fc1.weight", "offset": 4907488, "shape": [64, 256], "n": 16384},
  {"name": "rb4.se.fc1.bias", "offset": 4973024, "shape": [64], "n": 64},
  {"name": "rb4.se.fc2.weight", "offset": 4973280, "shape": [256, 64], "n": 16384},
  {"name": "rb4.se.fc2.bias", "offset": 5038816, "shape": [256], "n": 256},
  {"name": "lstm.fwd.weight_ih", "offset": 5039840, "shape": [512, 256], "n": 131072},
  {"name": "lstm.fwd.weight_hh", "offset": 5564128, "shape": [512, 128], "n": 65536},
  {"name": "lstm.fwd.bias", "offset": 5826272, "shape": [512], "n": 512},
  {"name": "lstm.bwd.weight_ih", "offset": 5828320, "shape": [512, 256], "n": 131072},
  {"name": "lstm.bwd.weight_hh", "offset": 6352608, "shape": [512, 128], "n": 65536},
  {"name": "lstm.bwd.bias", "offset": 6614752, "shape": [512], "n": 512},
  {"name": "fc.weight", "offset": 6616800, "shape": [29, 256], "n": 7424},
  {"name": "fc.bias", "offset": 6646496, "shape": [29], "n": 29}
]"""

    blob = blob_path.read_bytes()
    manifest = json.loads(weights_json)

    out = {}
    for entry in manifest:
        n = entry["n"]
        offset = entry["offset"]
        flat = list(struct.unpack_from(f"<{n}f", blob, offset))
        out[entry["name"]] = (flat, tuple(entry["shape"]))

    for name in list(out.keys()):
        flat, shape = out[name]
        if len(shape) == 4 and shape[2] == 3 and shape[3] == 3:
            out[name + "::wino"] = _wino_transform_weights(flat, shape[0], shape[1])

    if USE_MULTIPROCESSING:
        try:
            _warm_spawn_pool(out)
        except Exception:
            pass
    return out


def get_cached_weights():
    global _WEIGHTS_CACHE
    if _WEIGHTS_CACHE is None:
        _WEIGHTS_CACHE = load_weights()
    return _WEIGHTS_CACHE


def relu_inplace(x):
    x[:] = [v if v > 0.0 else 0.0 for v in x]


def sigmoid_list(x):
    fast_exp = math.exp
    return [1.0 / (1.0 + fast_exp(-v)) if v >= 0 else fast_exp(v) / (1.0 + fast_exp(v)) for v in x]


def maxpool(x, C, H, W, kh, kw):
    H2 = H // kh
    W2 = W // kw
    out = []
    app = out.append
    for c in range(C):
        base = c * H * W
        for i in range(H2):
            row = base + i * kh * W
            if kw == 2 and kh == 2:
                for j in range(W2):
                    idx = row + j * 2
                    app(max(x[idx], x[idx + 1], x[idx + W], x[idx + W + 1]))
            elif kw == 1 and kh == 2:
                for j in range(W2):
                    idx = row + j
                    app(max(x[idx], x[idx + W]))
            else:
                for j in range(W2):
                    idx = row + j * kw
                    app(max(x[idx + dh * W + dw] for dh in range(kh) for dw in range(kw)))
    return out


def avgpool_global_chw(x, C, H, W):
    HW = H * W
    inv = 1.0 / HW
    return [sum(x[c * HW: (c + 1) * HW]) * inv for c in range(C)]


def avgpool_h_to_1(x, C, H, W):
    inv = 1.0 / H
    out = []
    HW = H * W
    for c in range(C):
        base = c * HW
        out.extend(sum(x[base + j: base + j + HW: W]) * inv for j in range(W))
    return out


def _args_matmul_worker_oc(args):
    w, b, pixels, K = args
    dot = _dot
    out = []
    for oc in range(len(b)):
        w_oc = w[oc * K: (oc + 1) * K]
        bias = b[oc]
        out += [bias + dot(w_oc, p) for p in pixels]
    return out


def _args_matmul_worker_px(args):
    w, b, px_chunk, K, C_out = args
    dot = _dot
    out = []
    for oc in range(C_out):
        w_oc = w[oc * K: (oc + 1) * K]
        bias = b[oc]
        out += [bias + dot(w_oc, p) for p in px_chunk]
    return out


def _args_lstm_worker(args):
    direction, seq, w_ih, w_hh, b, hidden = args
    if direction == 0:
        return lstm_run(seq, w_ih, w_hh, b, hidden)
    out = lstm_run(seq[::-1], w_ih, w_hh, b, hidden)
    out.reverse()
    return out


def _wino_input_transform(d):
    a = []
    for v in range(6):
        d0 = d[v]; d1 = d[6 + v]; d2 = d[12 + v]
        d3 = d[18 + v]; d4 = d[24 + v]; d5 = d[30 + v]
        a.append([4.0 * p0 - 5.0 * p2 + p4 for p0, p2, p4 in zip(d0, d2, d4)])
        a.append([-4.0 * (p1 + p2) + p3 + p4 for p1, p2, p3, p4 in zip(d1, d2, d3, d4)])
        a.append([4.0 * (p1 - p2) - p3 + p4 for p1, p2, p3, p4 in zip(d1, d2, d3, d4)])
        a.append([-2.0 * p1 - p2 + 2.0 * p3 + p4 for p1, p2, p3, p4 in zip(d1, d2, d3, d4)])
        a.append([2.0 * p1 - p2 - 2.0 * p3 + p4 for p1, p2, p3, p4 in zip(d1, d2, d3, d4)])
        a.append([4.0 * p1 - 5.0 * p3 + p5 for p1, p3, p5 in zip(d1, d3, d5)])
    V = [None] * 36
    for r in range(6):
        a0 = a[r]; a1 = a[6 + r]; a2 = a[12 + r]
        a3 = a[18 + r]; a4 = a[24 + r]; a5 = a[30 + r]
        V[r * 6 + 0] = [4.0 * p0 - 5.0 * p2 + p4 for p0, p2, p4 in zip(a0, a2, a4)]
        V[r * 6 + 1] = [-4.0 * (p1 + p2) + p3 + p4 for p1, p2, p3, p4 in zip(a1, a2, a3, a4)]
        V[r * 6 + 2] = [4.0 * (p1 - p2) - p3 + p4 for p1, p2, p3, p4 in zip(a1, a2, a3, a4)]
        V[r * 6 + 3] = [-2.0 * p1 - p2 + 2.0 * p3 + p4 for p1, p2, p3, p4 in zip(a1, a2, a3, a4)]
        V[r * 6 + 4] = [2.0 * p1 - p2 - 2.0 * p3 + p4 for p1, p2, p3, p4 in zip(a1, a2, a3, a4)]
        V[r * 6 + 5] = [4.0 * p1 - 5.0 * p3 + p5 for p1, p3, p5 in zip(a1, a3, a5)]
    return V


def _wino_output_transform(M36):
    s = []
    for j in range(6):
        m0 = M36[j]; m1 = M36[6 + j]; m2 = M36[12 + j]
        m3 = M36[18 + j]; m4 = M36[24 + j]; m5 = M36[30 + j]
        s.append([p0 + p1 + p2 + p3 + p4 for p0, p1, p2, p3, p4 in zip(m0, m1, m2, m3, m4)])
        s.append([p1 - p2 + 2.0 * (p3 - p4) for p1, p2, p3, p4 in zip(m1, m2, m3, m4)])
        s.append([p1 + p2 + 4.0 * (p3 + p4) for p1, p2, p3, p4 in zip(m1, m2, m3, m4)])
        s.append([p1 - p2 + 8.0 * (p3 - p4) + p5 for p1, p2, p3, p4, p5 in zip(m1, m2, m3, m4, m5)])
    Y = []
    for r in range(4):
        s0 = s[r]; s1 = s[4 + r]; s2 = s[8 + r]
        s3 = s[12 + r]; s4 = s[16 + r]; s5 = s[20 + r]
        Y.append([p0 + p1 + p2 + p3 + p4 for p0, p1, p2, p3, p4 in zip(s0, s1, s2, s3, s4)])
        Y.append([p1 - p2 + 2.0 * (p3 - p4) for p1, p2, p3, p4 in zip(s1, s2, s3, s4)])
        Y.append([p1 + p2 + 4.0 * (p3 + p4) for p1, p2, p3, p4 in zip(s1, s2, s3, s4)])
        Y.append([p1 - p2 + 8.0 * (p3 - p4) + p5 for p1, p2, p3, p4, p5 in zip(s1, s2, s3, s4, s5)])
    return Y


def _wino_gather(pad_x, base, th, W2, xs, xe):
    Lw = xe - xs
    d = []
    off = 4 * xs
    for u in range(6):
        for v in range(6):
            row = []
            ext = row.extend
            for ty in range(th):
                s = base + (4 * ty + u) * W2 + v + off
                ext(pad_x[s: s + 4 * Lw: 4])
            d.append(row)
    return d


def _wino_tiles_pipeline(dloc, U36, C_in, C_out):
    V36 = [[] for _ in range(36)]
    for ic in range(C_in):
        V = _wino_input_transform(dloc[ic])
        for p in range(36):
            V36[p].append(V[p])
    dot = _dot
    M36 = []
    for p in range(36):
        tp = list(zip(*V36[p]))
        m = []
        for w_oc in U36[p]:
            m += [dot(w_oc, t) for t in tp]
        M36.append(m)
    return _wino_output_transform(M36)


def _args_wino_stripe_worker(args):
    key, pad_loc, b, C_in, C_out, th, Lw, H, H2, Wloc = args
    dloc = [_wino_gather(pad_loc, ic * H2 * Wloc, th, Wloc, 0, Lw) for ic in range(C_in)]
    Y16 = _wino_tiles_pipeline(dloc, _SPAWN_WINO[key], C_in, C_out)
    return _wino_stripe_block(Y16, b, C_out, H, th, Lw)


def _matmul_rows(w, b, pixels, K, C_out):
    if USE_MULTIPROCESSING:
        _init_mp()
        P = len(pixels)
        if _MP_CTX is not None and C_out >= 2 and C_out * P * K >= _MP_MIN_OPS:
            try:
                n_chunks = min(_MP_CORES, C_out)
                chunk = math.ceil(C_out / n_chunks)
                ranges = [(i, min(i + chunk, C_out)) for i in range(0, C_out, chunk)]
                pool = _get_persistent_pool()
                n = len(ranges)
                cost_oc = len(w) + n * P * K
                cost_px = n * len(w) + P * K
                if cost_oc <= cost_px:
                    tasks = [(w[s * K: e * K], b[s: e], pixels, K) for s, e in ranges]
                    chunks = pool.map(_args_matmul_worker_oc, tasks)
                    out = []
                    for c in chunks:
                        out += c
                    return out
                pchunk = math.ceil(P / n)
                pranges = [(i, min(i + pchunk, P)) for i in range(0, P, pchunk)]
                tasks = [(w, b, pixels[ps: pe], K, C_out) for ps, pe in pranges]
                chunks = pool.map(_args_matmul_worker_px, tasks)
                out = [0.0] * (C_out * P)
                for (ps, pe), res in zip(pranges, chunks):
                    L = pe - ps
                    for oc in range(C_out):
                        out[oc * P + ps: oc * P + pe] = res[oc * L: (oc + 1) * L]
                return out
            except Exception:
                pass

    dot = _dot
    out = []
    for oc in range(C_out):
        w_oc = w[oc * K: (oc + 1) * K]
        bias = b[oc]
        out += [bias + dot(w_oc, p) for p in pixels]
    return out


def conv2d_3x3_pad1(x, w, b, C_in, C_out, H, W):
    HW = H * W
    W2 = W + 2
    H2 = H + 2

    pad_row = [0.0] * W2
    pad_x = []
    for ic in range(C_in):
        in_base = ic * HW
        pad_x.extend(pad_row)
        for h in range(H):
            start = in_base + h * W
            pad_x.append(0.0)
            pad_x.extend(x[start: start + W])
            pad_x.append(0.0)
        pad_x.extend(pad_row)

    features = []
    for ic in range(C_in):
        pad_base = ic * H2 * W2
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                feat = []
                ext = feat.extend
                for h in range(H):
                    row_start = pad_base + (h + dy) * W2 + dx
                    ext(pad_x[row_start: row_start + W])
                features.append(feat)

    pixels = list(zip(*features))
    return _matmul_rows(w, b, pixels, C_in * 9, C_out)


def conv2d_1x1(x, w, b, C_in, C_out, H, W):
    HW = H * W
    x_pixels = [x[p:: HW] for p in range(HW)]
    return _matmul_rows(w, b, x_pixels, C_in, C_out)


def _wino_stripe_block(Y16, b, C_out, H, th, Lw):
    L = th * Lw
    W4 = 4 * Lw
    out = [0.0] * (C_out * H * W4)
    for oc in range(C_out):
        bias = b[oc]
        obase = oc * H * W4
        ybase = oc * L
        for ty in range(th):
            row0 = 4 * ty
            seg = ybase + ty * Lw
            for r in range(4):
                row = row0 + r
                if row >= H:
                    break
                rb = obase + row * W4
                for c in range(4):
                    yl = Y16[r * 4 + c]
                    out[rb + c: rb + W4: 4] = [v + bias for v in yl[seg: seg + Lw]]
    return out


def conv2d_3x3_wino(x, U36, b, C_in, C_out, H, W, key=None):
    HW = H * W
    th = (H + 3) // 4
    tw = W // 4
    T = th * tw
    Ht = 4 * th
    W2 = W + 2
    H2 = Ht + 2

    pad_row = [0.0] * W2
    extra = Ht - H
    pad_x = []
    for ic in range(C_in):
        in_base = ic * HW
        pad_x.extend(pad_row)
        for h in range(H):
            start = in_base + h * W
            pad_x.append(0.0)
            pad_x.extend(x[start: start + W])
            pad_x.append(0.0)
        for _ in range(extra + 1):
            pad_x.extend(pad_row)

    if USE_MULTIPROCESSING:
        _init_mp()
        parallel = (_MP_CTX is not None and tw >= 2 and _SPAWN_HAS_WINO
                    and key is not None and 36 * C_out * C_in * T >= _MP_MIN_OPS)
        if parallel:
            try:
                n = min(_MP_CORES, tw)
                chunk = math.ceil(tw / n)
                xranges = [(i, min(i + chunk, tw)) for i in range(0, tw, chunk)]
                pool = _get_persistent_pool()

                tasks = []
                for xs, xe in xranges:
                    Lw = xe - xs
                    Wloc = 4 * Lw + 2
                    col = 4 * xs
                    sub = []
                    ext = sub.extend
                    for ic in range(C_in):
                        cbase = ic * H2 * W2 + col
                        for r in range(H2):
                            s = cbase + r * W2
                            ext(pad_x[s: s + Wloc])
                    tasks.append((key, sub, b, C_in, C_out, th, Lw, H, H2, Wloc))
                chunks = pool.map(_args_wino_stripe_worker, tasks)

                out = [0.0] * (C_out * HW)
                for (xs, xe), blk in zip(xranges, chunks):
                    W4 = 4 * (xe - xs)
                    col = 4 * xs
                    for oc in range(C_out):
                        obase = oc * HW + col
                        bbase = oc * H * W4
                        for r in range(H):
                            s = obase + r * W
                            t = bbase + r * W4
                            out[s: s + W4] = blk[t: t + W4]
                return out
            except Exception:
                pass

    dloc = [_wino_gather(pad_x, ic * H2 * W2, th, W2, 0, tw) for ic in range(C_in)]
    Y16 = _wino_tiles_pipeline(dloc, U36, C_in, C_out)
    return _wino_stripe_block(Y16, b, C_out, H, th, tw)


def linear(x, w, b, in_f, out_f):
    dot = _dot
    n = len(x)
    return [b[o] + dot(w[o * in_f: o * in_f + n], x) for o in range(out_f)]


def se_block(x, weights, prefix, C, H, W):
    fc1_w, _ = weights[f"{prefix}.se.fc1.weight"]
    fc1_b, _ = weights[f"{prefix}.se.fc1.bias"]
    fc2_w, _ = weights[f"{prefix}.se.fc2.weight"]
    fc2_b, _ = weights[f"{prefix}.se.fc2.bias"]
    mid = len(fc1_b)

    pooled = avgpool_global_chw(x, C, H, W)
    h1 = linear(pooled, fc1_w, fc1_b, C, mid)
    relu_inplace(h1)
    h2 = linear(h1, fc2_w, fc2_b, mid, C)
    scale = sigmoid_list(h2)

    HW = H * W
    for c in range(C):
        s = scale[c]
        base = c * HW
        x[base: base + HW] = [v * s for v in x[base: base + HW]]
    return x


def resblock(x, weights, prefix, C_in, C_out, H, W, has_skip_conv):
    cw1, _ = weights[f"{prefix}.conv1.weight"]
    cb1, _ = weights[f"{prefix}.conv1.bias"]
    cw2, _ = weights[f"{prefix}.conv2.weight"]
    cb2, _ = weights[f"{prefix}.conv2.bias"]

    if has_skip_conv:
        sw, _ = weights[f"{prefix}.skip.weight"]
        sb, _ = weights[f"{prefix}.skip.bias"]
        residual = conv2d_1x1(x, sw, sb, C_in, C_out, H, W)
    else:
        residual = list(x)

    wino1 = weights.get(f"{prefix}.conv1.weight::wino")
    wino2 = weights.get(f"{prefix}.conv2.weight::wino")
    use_wino = (W % 4 == 0)

    if use_wino and C_in >= 16 and wino1 is not None:
        out = conv2d_3x3_wino(x, wino1, cb1, C_in, C_out, H, W,
                              key=f"{prefix}.conv1.weight::wino")
    else:
        out = conv2d_3x3_pad1(x, cw1, cb1, C_in, C_out, H, W)
    relu_inplace(out)
    if use_wino and wino2 is not None:
        out = conv2d_3x3_wino(out, wino2, cb2, C_out, C_out, H, W,
                              key=f"{prefix}.conv2.weight::wino")
    else:
        out = conv2d_3x3_pad1(out, cw2, cb2, C_out, C_out, H, W)
    se_block(out, weights, prefix, C_out, H, W)

    return [s if (s := o + r) > 0.0 else 0.0 for o, r in zip(out, residual)]


def lstm_run(seq, w_ih, w_hh, b, hidden):
    if not seq:
        return []
    input_size = len(seq[0])
    h = [0.0] * hidden
    c = [0.0] * hidden
    out = []

    H4 = 4 * hidden
    h0, h1, h2, h3 = 0, hidden, 2 * hidden, 3 * hidden

    w_ih_rows = [w_ih[r * input_size: (r + 1) * input_size] for r in range(H4)]
    w_hh_rows = [w_hh[r * hidden: (r + 1) * hidden] for r in range(H4)]

    fast_exp = math.exp
    fast_tanh = math.tanh
    dot = _dot

    proj = [[b[r] + dot(w_ih_rows[r], x_t) for r in range(H4)] for x_t in seq]

    for gates in proj:
        for r in range(H4):
            gates[r] += dot(w_hh_rows[r], h)

        new_h = [0.0] * hidden
        new_c = [0.0] * hidden
        for k in range(hidden):
            i = 1.0 / (1.0 + fast_exp(-gates[h0 + k]))
            f = 1.0 / (1.0 + fast_exp(-gates[h1 + k]))
            g = fast_tanh(gates[h2 + k])
            o = 1.0 / (1.0 + fast_exp(-gates[h3 + k]))

            new_c[k] = f * c[k] + i * g
            new_h[k] = o * fast_tanh(new_c[k])

        h, c = new_h, new_c
        out.append(h)
    return out


def ctc_greedy_decode(logits_tc):
    chars = []
    prev = -1
    for vec in logits_tc:
        best = max(range(len(vec)), key=vec.__getitem__)
        if best != prev and best != BLANK:
            chars.append(IDX_TO_CHAR[best])
        prev = best
    return "".join(chars)


def forward(x_chw, weights):
    out = resblock(x_chw, weights, "rb1", 3, 32, 48, 256, has_skip_conv=True)
    out = maxpool(out, 32, 48, 256, 2, 2)

    out = resblock(out, weights, "rb2", 32, 64, 24, 128, has_skip_conv=True)
    out = maxpool(out, 64, 24, 128, 2, 2)

    out = resblock(out, weights, "rb3", 64, 128, 12, 64, has_skip_conv=True)
    out = maxpool(out, 128, 12, 64, 2, 1)

    out = resblock(out, weights, "rb4", 128, 256, 6, 64, has_skip_conv=True)
    out = maxpool(out, 256, 6, 64, 2, 1)

    out = avgpool_h_to_1(out, 256, 3, 64)

    seq = [out[t:: 64] for t in range(64)]

    fwd_w_ih, _ = weights["lstm.fwd.weight_ih"]
    fwd_w_hh, _ = weights["lstm.fwd.weight_hh"]
    fwd_b, _ = weights["lstm.fwd.bias"]
    bwd_w_ih, _ = weights["lstm.bwd.weight_ih"]
    bwd_w_hh, _ = weights["lstm.bwd.weight_hh"]
    bwd_b, _ = weights["lstm.bwd.bias"]

    if USE_MULTIPROCESSING:
        _init_mp()
        if _MP_CTX is not None and _MP_CORES >= 2:
            try:
                pool = _get_persistent_pool()
                tasks = [
                    (0, seq, fwd_w_ih, fwd_w_hh, fwd_b, 128),
                    (1, seq, bwd_w_ih, bwd_w_hh, bwd_b, 128),
                ]
                fwd_out, bwd_out = pool.map(_args_lstm_worker, tasks)
            except Exception:
                fwd_out = lstm_run(seq, fwd_w_ih, fwd_w_hh, fwd_b, hidden=128)
                bwd_out = lstm_run(seq[::-1], bwd_w_ih, bwd_w_hh, bwd_b, hidden=128)
                bwd_out.reverse()
        else:
            fwd_out = lstm_run(seq, fwd_w_ih, fwd_w_hh, fwd_b, hidden=128)
            bwd_out = lstm_run(seq[::-1], bwd_w_ih, bwd_w_hh, bwd_b, hidden=128)
            bwd_out.reverse()
    else:
        fwd_out = lstm_run(seq, fwd_w_ih, fwd_w_hh, fwd_b, hidden=128)
        bwd_out = lstm_run(seq[::-1], bwd_w_ih, bwd_w_hh, bwd_b, hidden=128)
        bwd_out.reverse()

    rnn_out = [[f + bw for f, bw in zip(f_vec, bw_vec)] for f_vec, bw_vec in zip(fwd_out, bwd_out)]

    fc_w, _ = weights["fc.weight"]
    fc_b, _ = weights["fc.bias"]
    logits = [linear(v, fc_w, fc_b, 256, NUM_CLASSES) for v in rnn_out]
    return logits


def predict(x_chw, weights):
    return ctc_greedy_decode(forward(x_chw, weights))


def read_png(image_bytes):
    with io.BytesIO(image_bytes) as f:
        if f.read(8) != b'\x89PNG\r\n\x1a\n':
            raise ValueError("Not a valid PNG file. Only PNG images are supported.")

        palette = None
        idat = bytearray()

        while True:
            length_bytes = f.read(4)
            if not length_bytes:
                break
            length = struct.unpack('>I', length_bytes)[0]
            chunk_type = f.read(4)
            chunk_data = f.read(length)
            f.read(4)

            if chunk_type == b'IHDR':
                width, height, bit_depth, color_type, comp, fltr, interlace = struct.unpack('>IIBBBBB', chunk_data)
                if comp != 0 or fltr != 0:
                    raise ValueError("Unsupported PNG compression or filter method.")
                if interlace != 0:
                    raise ValueError("Interlaced PNGs are not supported.")
                if bit_depth == 16:
                    raise ValueError("16-bit PNGs are not supported.")
            elif chunk_type == b'PLTE':
                palette = chunk_data
            elif chunk_type == b'IDAT':
                idat.extend(chunk_data)
            elif chunk_type == b'IEND':
                break

    decompressed = zlib.decompress(idat)

    if color_type == 2: bpp = 3
    elif color_type == 6: bpp = 4
    elif color_type in (0, 3): bpp = 1
    else: raise ValueError(f"Unsupported color type {color_type}")

    row_bytes = (width * bpp * bit_depth + 7) // 8
    bpp_bytes = max(1, (bpp * bit_depth + 7) // 8)

    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        if pa <= pb and pa <= pc: return a
        if pb <= pc: return b
        return c

    pixels = bytearray()
    prev_row = bytearray(row_bytes)
    idx = 0

    for _ in range(height):
        filter_type = decompressed[idx]
        idx += 1
        row = decompressed[idx: idx + row_bytes]
        idx += row_bytes

        unfiltered = bytearray(row_bytes)
        for x in range(row_bytes):
            left = unfiltered[x - bpp_bytes] if x >= bpp_bytes else 0
            up = prev_row[x]
            up_left = prev_row[x - bpp_bytes] if x >= bpp_bytes else 0

            if filter_type == 0: val = row[x]
            elif filter_type == 1: val = row[x] + left
            elif filter_type == 2: val = row[x] + up
            elif filter_type == 3: val = row[x] + (left + up) // 2
            elif filter_type == 4: val = row[x] + paeth(left, up, up_left)
            else: raise ValueError(f"Invalid filter type {filter_type}")

            unfiltered[x] = val & 0xFF

        pixels.extend(unfiltered)
        prev_row = unfiltered

    rgb_pixels = []
    if color_type == 2:
        for i in range(0, len(pixels), 3):
            rgb_pixels.append((pixels[i], pixels[i+1], pixels[i+2]))
    elif color_type == 6:
        for i in range(0, len(pixels), 4):
            rgb_pixels.append((pixels[i], pixels[i+1], pixels[i+2]))
    elif color_type == 0:
        if bit_depth == 8:
            for p in pixels:
                rgb_pixels.append((p, p, p))
        else:
            mask = (1 << bit_depth) - 1
            for i in range(height):
                row_start = i * row_bytes
                row_data = pixels[row_start: row_start + row_bytes]
                x = 0
                for byte in row_data:
                    for shift in range(8 - bit_depth, -1, -bit_depth):
                        if x < width:
                            val = ((byte >> shift) & mask) * 255 // mask
                            rgb_pixels.append((val, val, val))
                            x += 1
    elif color_type == 3:
        mask = (1 << bit_depth) - 1
        for i in range(height):
            row_start = i * row_bytes
            row_data = pixels[row_start: row_start + row_bytes]
            x = 0
            for byte in row_data:
                for shift in range(8 - bit_depth, -1, -bit_depth):
                    if x < width:
                        idx_val = (byte >> shift) & mask
                        r = palette[idx_val*3]
                        g = palette[idx_val*3+1]
                        b = palette[idx_val*3+2]
                        rgb_pixels.append((r, g, b))
                        x += 1

    return width, height, rgb_pixels


def preprocess_image(image_bytes):
    width, height, rgb_pixels = read_png(image_bytes)

    target_w = IMG_W
    target_h = IMG_H

    x_ratio = width / float(target_w)
    y_ratio = height / float(target_h)

    x_coords = []
    for dx in range(target_w):
        sx = (dx + 0.5) * x_ratio - 0.5
        x0 = max(0, int(sx))
        x1 = min(x0 + 1, width - 1)
        wx = max(0.0, sx - x0)
        x_coords.append((x0, x1, wx, 1.0 - wx))

    y_coords = []
    for dy in range(target_h):
        sy = (dy + 0.5) * y_ratio - 0.5
        y0 = max(0, int(sy))
        y1 = min(y0 + 1, height - 1)
        wy = m
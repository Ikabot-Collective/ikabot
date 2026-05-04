import os
import struct
import zlib
import io
import requests

try:
    from onnxruntime_inference_collection import InferenceSession # Ignore, this only works if you have the onnxruntime_pybind11_state.pyd file for win
except:                                                           # or onnxruntime_pybind11_state.cpython-310-x86_64-linux-gnu.so for linux
    try:
        from onnxruntime import InferenceSession
    except:
        print('ERROR: COULD NOT FIND ONNXRUNTIME INFERENCE SESSION!')
        raise

if os.name == 'nt':
    _temp = os.getenv('temp') or os.getenv('TMP') or os.getenv('TEMP') or '.'
    _model_cache_path = _temp + '/ikabot_ikaptcha.onnx'
else:
    _model_cache_path = '/tmp/ikabot_ikaptcha.onnx'

_url = 'https://github.com/Ikabot-Collective/IkabotAPI/raw/4ebe57a3f1c11acb357a4bf4b6f7f92e1da287ce/apps/decaptcha/pirates_captcha/ikaptcha.onnx'
session = None


def _load_model():
    global session
    if session is not None:
        return session

    if os.path.isfile(_model_cache_path):
        try:
            with open(_model_cache_path, 'rb') as f:
                cached = f.read()
            session = InferenceSession(cached)
            return session
        except Exception:
            try:
                os.remove(_model_cache_path)
            except Exception:
                pass

    try:
        print('Downloading .onnx model, please wait...')
        resp = requests.get(_url, timeout=30)
        resp.raise_for_status()
        model_bytes = resp.content
    except Exception as e:
        raise RuntimeError('Failed to download the ONNX model from ' + _url) from e

    try:
        with open(_model_cache_path, 'wb') as f:
            f.write(model_bytes)
    except Exception:
        pass

    session = InferenceSession(model_bytes)
    return session


# CRNN charset. CTC blank lives at index 0, so character k corresponds to VOCAB[k-1].
VOCAB = "abcdefghjklmnpqrstuvwxy23457"


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
            f.read(4)  # CRC

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
        row = decompressed[idx : idx + row_bytes]
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

    rgb_pixels =[]
    if color_type == 2:  # RGB
        for i in range(0, len(pixels), 3):
            rgb_pixels.append((pixels[i], pixels[i+1], pixels[i+2]))
    elif color_type == 6:  # RGBA
        for i in range(0, len(pixels), 4):
            rgb_pixels.append((pixels[i], pixels[i+1], pixels[i+2]))
    elif color_type == 0:  # Grayscale
        if bit_depth == 8:
            for p in pixels:
                rgb_pixels.append((p, p, p))
        else:
            mask = (1 << bit_depth) - 1
            for i in range(height):
                row_start = i * row_bytes
                row_data = pixels[row_start : row_start + row_bytes]
                x = 0
                for byte in row_data:
                    for shift in range(8 - bit_depth, -1, -bit_depth):
                        if x < width:
                            val = ((byte >> shift) & mask) * 255 // mask
                            rgb_pixels.append((val, val, val))
                            x += 1
    elif color_type == 3:  # Indexed (Palette)
        mask = (1 << bit_depth) - 1
        for i in range(height):
            row_start = i * row_bytes
            row_data = pixels[row_start : row_start + row_bytes]
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


def _resize_and_normalize(width, height, rgb_pixels, target_h=48, target_w=256):
    """Bilinear resize to (target_h, target_w), normalize to [-1, 1], return CHW float blob."""
    x_ratio = width / target_w
    y_ratio = height / target_h

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
        wy = max(0.0, sy - y0)
        y_coords.append((y0 * width, y1 * width, wy, 1.0 - wy))

    r = [[0.0] * target_w for _ in range(target_h)]
    g = [[0.0] * target_w for _ in range(target_h)]
    b = [[0.0] * target_w for _ in range(target_h)]

    inv = 1.0 / 127.5
    for dy in range(target_h):
        y0_off, y1_off, wy, wy_inv = y_coords[dy]
        r_row, g_row, b_row = r[dy], g[dy], b[dy]

        for dx in range(target_w):
            x0, x1, wx, wx_inv = x_coords[dx]

            w00 = wx_inv * wy_inv
            w01 = wx * wy_inv
            w10 = wx_inv * wy
            w11 = wx * wy

            p00 = rgb_pixels[y0_off + x0]
            p01 = rgb_pixels[y0_off + x1]
            p10 = rgb_pixels[y1_off + x0]
            p11 = rgb_pixels[y1_off + x1]

            r_row[dx] = (p00[0]*w00 + p01[0]*w01 + p10[0]*w10 + p11[0]*w11) * inv - 1.0
            g_row[dx] = (p00[1]*w00 + p01[1]*w01 + p10[1]*w10 + p11[1]*w11) * inv - 1.0
            b_row[dx] = (p00[2]*w00 + p01[2]*w01 + p10[2]*w10 + p11[2]*w11) * inv - 1.0

    return [[r, g, b]]


def _ctc_greedy_decode(logits_tbc):
    """Greedy CTC decode on logits with shape (T, B=1, C). Returns the decoded string."""
    chars = []
    prev = -1
    for t in range(len(logits_tbc)):
        vec = logits_tbc[t][0]
        best = 0
        best_v = vec[0]
        for k in range(1, len(vec)):
            if vec[k] > best_v:
                best_v = vec[k]
                best = k
        if best != prev and best != 0:  # 0 is the CTC blank
            chars.append(VOCAB[best - 1])
        prev = best
    return "".join(chars)


def get_captcha_string(image_bytes):
    """Return the captcha text for a given image."""
    width, height, rgb_pixels = read_png(image_bytes)

    assert height <= 100 and width <= 500, "Image is too large"

    blob = _resize_and_normalize(width, height, rgb_pixels)

    sess = _load_model()
    input_name = sess.get_inputs()[0].name
    logits = sess.run(None, {input_name: blob})[0]  # (T, B, C)

    return _ctc_greedy_decode(logits).upper()

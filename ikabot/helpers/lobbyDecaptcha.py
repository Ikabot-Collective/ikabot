import os
import struct
import zlib
from base64 import b64encode
from time import time

#   ICON BASE64 HASH        TUPLE OF TEXTS ASSOCIATED WITH ICON         (multiple mappings may exist for each individual icon due to uncertainty of the anti-aliasing that happens on GF servers)
icons_to_texts = {
    "+PZPBAAAAwMIBAzlJm2o": ("/vj34N3o5+vr4+f++/wA", "/vf24N/m5urq5eb9/PwA"),
    "23nx7oteW3n45krqB7Vw": (
        "/vb13dzk5ubl297++fkA",
        "APb03uDm5+fm2t4AAAAA",
        "/vf23tzl5ubk3N79+foA",
    ),
    "31IyUgYCaWDPALimKmb+": ("/vX03+Hq4+jq2dsAAAAA", "/vb04N/s4+jq2NsAAAAA"),
    "5qov13hCSRKlpIZrkxi7": ("+/X249vo4+vr3OL++/wA", "/PX34ODh4Ofn3t/9/PwA"),
    "AAYrIpL6NH9L8Cl3NQw8": ("/PX049/o4ufm2t4AAAAA", "/PX04+Dn4OXn2t4AAAAA"),
    "Ayofi65ARKfuEiQdDvnd": ("APf23d/t6enq3eAAAAAA", "APj23N7r6enq3eAAAAAA"),
    "CBIWFA0A9d29on1PJPC3": ("/PX14Nvl4OPk298AAAAA", "/PX039ri3uLj2twAAAAA"),
    "CKBiaqxhODImGhAMEhIS": ("/Pb15ODr5erq3d8AAAAA", "/PX04uHo4+jo3uAAAAAA"),
    "Cw/sc8MQU5LnRrI5v2RU": ("APn43tnk2d/i2dkAAAAA", "APn53trr3uHk298AAAAA"),
    "DkFxnMHf9xAeJS0yMC85": ("APn53trh4eHi3OAAAAAA", "APr539vi4+Pk3+IAAAAA"),
    "FsBAjO3/nRh7UYIGrSUC": ("/PHz5OTn5+rp3d79+foA", "+/Dw4eHl5ejo2t3++fkA"),
    "HqQpk9QkVGVxWksd0443": ("+/X229nj4uPl3d8AAAAA", "/PX33Nvm4+Pk3+AAAAAA"),
    "In9Lr7PjGEx+j9TIt2EJ": ("/vr6397l4eXl3uAAAAAA", "/vn53tzh3+Tk3t8AAAAA"),
    "JW1v1cHMWVqHW6DCdCPw": ("/vf24N3q3OHn1tgAAAAA", "/vf239zs2+Ho1tgAAAAA"),
    "K0cwDcaki4WGhpSy5jEe": ("APn54d7k5OTl3eH++fkA", "APr54d/j5eXk4OH9+foA"),
    "Li80NTg4Oz0+Pjs5NdUy": ("APDv4eHj4OXl3+H+/v4A", "APLy4+Tp5enq4eT+/v4A"),
    "M+l9yVF6a9Hf08q4o35e": ("/vv74d/m4+fl3eL8/PwA", "/vz64dzj5OXi3N78/PwA"),
    "NTJlQAfFmLDp8Gc7wejy": ("/O3t3t/h3Orq4uQAAAAA", "/e/w4eTk3+zt5ucAAAAA"),
    "O3G4AzZUZW96hqJEJp5B": ("/vPz3uDj4Ojo2t0AAAAA", "/vPw3dzj3+fm19wAAAAA"),
    "OR+F2DNOk6G0qsZLrtHu": ("/vj44eDd2+fn4uYAAAAA", "/vf34Nvh3+bm4uUAAAAA"),
    "Ocsx+FMQwp381bi380ja": ("/PDy4+Pg4O3r4uL/+/sA", "++7w4+Dj4e7t3+IA+/sA"),
    "Pnm4gE9CXJLXYFb/jYBr": ("/vb339/m5Onp3uAAAAAA", "/fb2393n5ero3OAAAAAA"),
    "Qz1BtMm8spx7Wy37vnks": ("APr63uDl3+jp4OIAAAAA", "APn43t3j3efn3eAAAAAA"),
    "SeSMR/Sqc0kZ/N3MppS2": ("+vP24+Ho5efn4OH9+foA", "+PP25eLn5Ofp3+H++fkA"),
    "Vo2s1OsCFSg+YHORq9MJ": ("/PPz4eDj4Ojo3+EAAAAA", "/PPx393j4Ojn3N8AAAAA"),
    "YqD/fo6SaYJCNwHz5FTn": ("/vb13uDm4err4uMAAAAA", "/vXz3dzk3+np3uEAAAAA"),
    "bcQHDBEMBc+9fzTfc/WQ": ("APn43dro4+fn3N/++fkA", "APn33Nzm4efm3eD9+foA"),
    "dfeYGYKgEfkZYJ+NwLBd": ("APb349/v5vDv3d4AAAAA", "APT24OHq4uzt3dwAAAAA"),
    "dnFhxCdeFMjboa7rN/7h": ("/fj529nm4uXs2NsAAAAA", "/vj53Njm4+bq19gAAAAA"),
    "dvFKfY9ejtvHwvkhSyVZ": ("/fX14uTt5ufp3OAAAAAA", "/vX24uXu5eXn3N4AAAAA"),
    "iYeHh4eHh4eHh4eHh4eH": ("/vj34N3n5eno2d0AAAAA",),
    "k2epIVghl3yjDUx9kJ+s": ("APv739zk4ubn4eL9/PwA", "APr53Nnl3+Tm3eD++/wA"),
    "lWLxIJaaxQZWuRIEH0V9": ("APb13d/q5ujp3uAAAAAA", "APbz3N7k4uXn3OAAAAAA"),
    "m4x8cndnXV9jXFhXVlda": ("APf23Nnj3OLj2d3++fkA", "APj32tzi3uPk3d79+foA"),
    "oObRbENHF+gcatya2OtU": ("APj34uHo6Orp3+AAAAAA", "APj24eHj5efo3eEAAAAA"),
    "pgHHgbRVvMDYssvBUzAp": ("/PT13N3n5Ojp4uQAAAAA", "+/Pz19rf3+Tk3+EAAAAA"),
    "ubm4vLq8ury+wbzAwb7C": ("/vf33tnh4ePj2t4AAAAA", "/vf23djg4ePj2t0AAAAA"),
    "vn6fEoAKgDD0xJt+Zk03": ("+/X23Nnf3t7f29wAAAAA", "/PX339zk4OHj3OAAAAAA"),
    "vreuppmWf243MC7Gw7Cw": ("APz84ODr5+fo2d38/PwA", "APv63t7l4+Tj19r8/PwA"),
    "whJsa5CySTovcqJI9ZKx": ("APf339zn4+3r4eQAAAAA", "APj44N/n4+3t5eYAAAAA"),
    "wjeUAIkmznz/Q0tKPQ9U": ("APr539zm6OXm4eMAAAAA", "APn44d/k5Ofn3+QAAAAA"),
    "xgMqGmp0UJYIohqocUJM": ("APn43dzq3ODk2Nz+/v4A", "APn439vq3uTl2tz+/v4A"),
    "xgpFi5avYcTSqbE/b0WT": ("/PX05OLn6Ojm2t0AAAAA", "/Pb15eLq6unp298AAAAA"),
    "yatBgon7woVQMiQeIyo6": ("/vb23t3j5Ofn4+UAAAAA", "/vb13Nzf4uXl4eQAAAAA"),
}


class SimpleImage:
    def __init__(self, width, height, pixels, mode, palette=None):
        self.width = width
        self.height = height
        self.pixels = pixels
        self.mode = mode
        self.palette = palette
        self.size = (width, height)
        
    def getpixel(self, xy):
        x, y = int(xy[0]), int(xy[1])
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError("image index out of range")
            
        if self.mode == 'RGBA':
            idx = (y * self.width + x) * 4
            return tuple(self.pixels[idx:idx+4])
        elif self.mode == 'RGB':
            idx = (y * self.width + x) * 3
            return tuple(self.pixels[idx:idx+3])
        elif self.mode == 'LA':
            idx = (y * self.width + x) * 2
            return tuple(self.pixels[idx:idx+2])
        elif self.mode in ('L', 'P'):
            idx = y * self.width + x
            return self.pixels[idx]
            
    def crop(self, box):
        left, upper, right, lower = map(int, box)
        new_width = right - left
        new_height = lower - upper
        
        if self.mode == 'RGBA': bpp = 4
        elif self.mode == 'RGB': bpp = 3
        elif self.mode == 'LA': bpp = 2
        elif self.mode in ('L', 'P'): bpp = 1
            
        new_pixels = bytearray(new_width * new_height * bpp)
        
        for y in range(new_height):
            src_y = upper + y
            if 0 <= src_y < self.height:
                src_x_start = max(0, left)
                src_x_end = min(self.width, right)
                
                if src_x_start < src_x_end:
                    src_idx = (src_y * self.width + src_x_start) * bpp
                    dst_x_start = src_x_start - left
                    dst_idx = (y * new_width + dst_x_start) * bpp
                    
                    length = (src_x_end - src_x_start) * bpp
                    new_pixels[dst_idx:dst_idx + length] = self.pixels[src_idx:src_idx + length]
            
        return SimpleImage(new_width, new_height, new_pixels, self.mode, self.palette)
        
    def convert(self, mode):
        if self.mode == mode:
            return self
            
        if mode == 'L':
            new_pixels = bytearray(self.width * self.height)
            if self.mode == 'RGBA':
                for i in range(self.width * self.height):
                    r = self.pixels[i*4]
                    g = self.pixels[i*4+1]
                    b = self.pixels[i*4+2]
                    new_pixels[i] = (r * 19595 + g * 38470 + b * 7471 + 32768) >> 16
            elif self.mode == 'RGB':
                for i in range(self.width * self.height):
                    r = self.pixels[i*3]
                    g = self.pixels[i*3+1]
                    b = self.pixels[i*3+2]
                    new_pixels[i] = (r * 19595 + g * 38470 + b * 7471 + 32768) >> 16
            elif self.mode == 'LA':
                for i in range(self.width * self.height):
                    new_pixels[i] = self.pixels[i*2]
            elif self.mode == 'P':
                l_palette =[]
                for rgb in self.palette:
                    r, g, b = rgb[0], rgb[1], rgb[2]
                    l = (r * 19595 + g * 38470 + b * 7471 + 32768) >> 16
                    l_palette.append(l)
                for i in range(self.width * self.height):
                    idx = self.pixels[i]
                    new_pixels[i] = l_palette[idx] if idx < len(l_palette) else 0
            return SimpleImage(self.width, self.height, new_pixels, 'L')
        else:
            raise NotImplementedError(f"Conversion from {self.mode} to {mode} not implemented")


def open_image(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError("Not a valid PNG")
    
    offset = 8
    chunks =[]
    while offset < len(data):
        length = struct.unpack('>I', data[offset:offset+4])[0]
        chunk_type = data[offset+4:offset+8]
        chunk_data = data[offset+8:offset+8+length]
        chunks.append((chunk_type, chunk_data))
        offset += 12 + length
        if chunk_type == b'IEND':
            break
            
    ihdr = [c[1] for c in chunks if c[0] == b'IHDR'][0]
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack('>IIBBBBB', ihdr)
    
    if compression != 0 or filter_method != 0 or interlace != 0:
        raise NotImplementedError("Unsupported PNG format")
        
    idat = b''.join([c[1] for c in chunks if c[0] == b'IDAT'])
    decompressed = zlib.decompress(idat)
    
    if color_type == 0: bpp = 1; mode = 'L'
    elif color_type == 2: bpp = 3; mode = 'RGB'
    elif color_type == 3: bpp = 1; mode = 'P'
    elif color_type == 4: bpp = 2; mode = 'LA'
    elif color_type == 6: bpp = 4; mode = 'RGBA'
    else: raise ValueError("Unknown color type")
    
    if bit_depth != 8:
        raise NotImplementedError("Only 8-bit depth supported")
        
    pixels = bytearray()
    stride = width * bpp
    i = 0
    prev_line = bytearray(stride)
    
    for y in range(height):
        filter_type = decompressed[i]
        i += 1
        line = bytearray(decompressed[i:i+stride])
        i += stride
        
        if filter_type == 0:
            pass
        elif filter_type == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x-bpp]) & 0xff
        elif filter_type == 2:
            for x in range(stride):
                line[x] = (line[x] + prev_line[x]) & 0xff
        elif filter_type == 3:
            for x in range(stride):
                left = line[x-bpp] if x >= bpp else 0
                up = prev_line[x]
                line[x] = (line[x] + (left + up) // 2) & 0xff
        elif filter_type == 4:
            for x in range(stride):
                a = line[x-bpp] if x >= bpp else 0
                b = prev_line[x]
                c = prev_line[x-bpp] if x >= bpp else 0
                p = a + b - c
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                line[x] = (line[x] + pr) & 0xff
                
        pixels.extend(line)
        prev_line = line
        
    if color_type == 3:
        plte = [c[1] for c in chunks if c[0] == b'PLTE'][0]
        palette =[plte[i:i+3] for i in range(0, len(plte), 3)]
        return SimpleImage(width, height, pixels, 'P', palette=palette)
        
    return SimpleImage(width, height, pixels, mode)


def image_hash(image):
    """Will output a "hash" of a greyscale image. The hash is actually just a tuple containg 15 numbers, each of which is the sum of all the pixels in that row modulated by 256. A pixel is just a number between 0 and 255.
    This tuple is then converted into a base64 string, because it is easier to store it in this file.
    """
    sum_vals = [0] * 15
    for i in range(0, 15):
        for j in range(0, image.size[0]):
            sum_vals[i] = (sum_vals[i] + image.getpixel((j, i))) % 256
    return b64encode(bytes(tuple(sum_vals))).decode("ascii")


def cut_text(image):
    """Takes in the image containing text and cuts in strategically and turns it into greyscale"""
    crop_x = 0
    # find left edge of the letter D to undo centering
    for i in range(0, 100):
        if image.getpixel((i, 7)) != (0, 0, 0, 0):
            crop_x = i - 1
            break
    image = image.crop((crop_x + 60, 0, crop_x + 115, 15))
    image = image.convert("L")
    return image


def cut_drag(image):
    """Takes in a drag icons image that contains 4 other images, cuts it up strategically, turns it into greyscale and returns a tuple containg the 4 seperate images."""
    image = image.crop((0, 22, image.size[0], 37))
    image = image.convert("L")
    return (
        image.crop((image.size[0] / 4 * 0, 0, image.size[0] / 4 * 1, image.size[1])),
        image.crop((image.size[0] / 4 * 1, 0, image.size[0] / 4 * 2, image.size[1])),
        image.crop((image.size[0] / 4 * 2, 0, image.size[0] / 4 * 3, image.size[1])),
        image.crop((image.size[0] / 4 * 3, 0, image.size[0] / 4 * 4, image.size[1])),
    )


def break_interactive_captcha(text_image, drag_icons):
    """This function will attempt to break the interactive captcha by finding the index of the icon specified by the text inside of the text_image image.
    Parameters
    ----------
    text_image : bytes
        bytes of text_image
    drag_icons : bytes
        bytes of darg_icons
    Returns
    -------
    index : int
        index of the exact image refrenced to by the text in text_image that is contained in the four images in drag_icons
    """

    if isinstance(text_image, (bytes, bytearray)):
        text_image = open_image(text_image)
        assert (
            text_image.size[0] == 330
        ), "Failed to convert text image bytes into Image object"
    if isinstance(drag_icons, (bytes, bytearray)):
        drag_icons = open_image(drag_icons)
        assert drag_icons.size == (
            240,
            60,
        ), "Failed to convert drag icons bytes into Image object"

    text_image_old = text_image
    text_image = cut_text(text_image)
    text_image_hash = image_hash(text_image)

    target = ""

    for key, value in icons_to_texts.items():
        if text_image_hash in value:
            target = key

    assert target != "", "Couldn't find text image in local store"

    i = 0
    for icon in cut_drag(drag_icons):
        if image_hash(icon) == target:
            return i
        i += 1

    raise Exception("Couldn't find icon image in local store")
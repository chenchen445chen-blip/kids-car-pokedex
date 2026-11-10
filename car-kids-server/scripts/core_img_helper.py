import struct


def get_img_dimensions(raw_bytes: bytes) -> tuple[int, int]:
    if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n") and len(raw_bytes) >= 24:
        w, h = struct.unpack(">II", raw_bytes[16:24])
        return int(w), int(h)
    if raw_bytes.startswith(b"\xff\xd8") and len(raw_bytes) > 4:
        idx = 2
        size = len(raw_bytes)
        while idx < size - 9:
            if raw_bytes[idx] != 0xFF:
                idx += 1
                continue
            marker = raw_bytes[idx + 1]
            while marker == 0xFF and idx + 2 < size:
                idx += 1
                marker = raw_bytes[idx + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                h, w = struct.unpack(">HH", raw_bytes[idx + 5 : idx + 9])
                return int(w), int(h)
            if marker in (0xD8, 0xD9, 0x01) or (0xD0 <= marker <= 0xD7):
                idx += 2
                continue
            if idx + 4 >= size:
                break
            seg_len = struct.unpack(">H", raw_bytes[idx + 2 : idx + 4])[0]
            idx += 2 + seg_len
    return 800, 600


"""Export video/GIF frames as a standalone, text-based HTML animation."""
import json
import math
import os
import tempfile
from pathlib import Path

import cv2
from PIL import Image, ImageColor


class ExportCancelled(Exception):
    pass


def media_frame_count(path):
    """Read timeline bounds without converting any frames to ASCII."""
    with open(path, 'rb') as source:
        is_gif = source.read(6) in (b'GIF87a', b'GIF89a')
    if is_gif:
        with Image.open(path) as source:
            return source.n_frames
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError('无法打开视频，请检查文件格式。')
        count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(count) or count < 1:
            raise ValueError('无法读取视频总帧数。')
        return int(count)
    finally:
        capture.release()


def preview_frame(path, index, settings, cell_size):
    """Use exactly the same decoded image and ASCII conversion as export."""
    iterator = media_frames(path, [index, index + 1])
    try:
        try:
            image, duration, _, _ = next(iterator)
        except StopIteration:
            raise ValueError('所选帧不存在，请重新加载文件。') from None
        return image, ascii_frame(image, settings, cell_size), duration
    finally:
        iterator.close()


def frame_range(interval):
    if interval in (None, '', 'None'):
        return 0, None
    if (not isinstance(interval, (list, tuple)) or len(interval) != 2
            or any(type(x) is not int for x in interval)
            or not 0 <= interval[0] < interval[1]):
        raise ValueError('帧范围应为 [起始帧, 结束帧]，从 0 开始，不含结束帧；留空导出全部。')
    return tuple(interval)


def media_frames(path, interval=None):
    start, end = frame_range(interval)
    # Detect GIF by content, including files with a nonstandard extension.
    with open(path, 'rb') as source:
        is_gif = source.read(6) in (b'GIF87a', b'GIF89a')
    if is_gif:
        with Image.open(path) as source:
            total = source.n_frames
            stop = total if end is None else min(end, total)
            for index in range(stop):
                source.seek(index)  # Pillow applies GIF disposal and frame composition.
                if index >= start:
                    duration = source.info.get('duration', 100) or 100
                    yield source.convert('RGBA'), duration, index - start + 1, stop - start
    else:
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise ValueError('无法打开视频，请检查文件格式。')
            fps = capture.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(fps) or fps <= 0:
                raise ValueError('无法读取视频帧率。')
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if start and not capture.set(cv2.CAP_PROP_POS_FRAMES, start):
                raise ValueError('无法定位到指定起始帧。')
            index = start
            while end is None or index < end:
                ok, frame = capture.read()
                if not ok:
                    if total > 0 and index < (total if end is None else min(end, total)):
                        raise ValueError(f'视频第 {index} 帧读取失败。')
                    break
                yield Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), 1000 / fps, index - start + 1, max(0, (min(end, total) if end else total) - start)
                index += 1
        finally:
            capture.release()


def css_color(value):
    if isinstance(value, int):
        value = (value,) * 3
    if isinstance(value, str):
        value = ImageColor.getrgb(value)
    return '#{:02x}{:02x}{:02x}'.format(*value[:3])


def ascii_frame(image, settings, cell_size):
    ratio = float(settings['resize_ratio'])
    width_ratio = float(settings['image_width_ratio'])
    height_ratio = float(settings['image_height_ratio'])
    if any(not math.isfinite(x) or x <= 0 for x in (ratio, width_ratio, height_ratio)):
        raise ValueError('缩放倍数和宽高比例必须为正数。')
    charset = settings['ascii_character_set']
    if not isinstance(charset, str) or not charset or any(c in charset for c in '\n\r\t'):
        raise ValueError('字符集不能为空或含换行符、制表符。')
    bits = settings['bit_number']
    if type(bits) is not int or not 1 <= bits <= 16:
        raise ValueError('位数必须为 1 到 16 的整数。')
    width = max(1, int(image.width / cell_size[0] * width_ratio / ratio))
    height = max(1, int(image.height / cell_size[1] * height_ratio / ratio))
    pixels = image.convert('RGBA').resize((width, height), Image.Resampling.LANCZOS)
    unit = (2 ** bits + 1) / len(charset)
    rows, colors = [], []
    for y in range(height):
        row = []
        for x in range(width):
            r, g, b, a = pixels.getpixel((x, y))
            gray = int(.2126 * r + .7152 * g + .0722 * b)
            row.append(' ' if a == 0 else charset[min(len(charset) - 1, int(gray / unit))])
            if settings['colored_image']:
                colors.append(css_color((r, g, b)))
        rows.append(''.join(row))
    return {'text': '\n'.join(rows), 'colors': colors}


def export_html(source, destination, settings, cell_size, progress=None, cancelled=None):
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError('输出文件不能覆盖输入文件。')
    frames = []
    iterator = media_frames(source, settings.get('video_frames_interval'))
    try:
        for image, duration, index, total in iterator:
            if cancelled and cancelled():
                raise ExportCancelled()
            frame = ascii_frame(image, settings, cell_size)
            frame['duration'] = duration
            frames.append(frame)
            if progress:
                progress(index, total)
    finally:
        iterator.close()
    if not frames:
        raise ValueError('没有可导出的帧，请检查文件及帧范围。')
    data = {'frames': frames, 'foreground': css_color(settings['ascii_image_character_color']),
            'background': css_color(settings['ascii_image_init_bg_color'])}
    # JSON script content must not allow a custom ASCII charset to end the tag.
    payload = json.dumps(data, ensure_ascii=True, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = Path(__file__).with_name('ascii_player.html').read_text(encoding='utf-8')
    html = template.replace('__ASCII_DATA__', payload)
    if cancelled and cancelled():
        raise ExportCancelled()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=Path(destination).parent,
                                         suffix='.tmp', delete=False) as output:
            temporary = output.name
            output.write(html)
        if cancelled and cancelled():
            raise ExportCancelled()
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return len(frames)

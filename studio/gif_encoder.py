"""Incremental GIF encoding: keep only the current raster frame in memory."""
import io
from pathlib import Path
import threading

from PIL import GifImagePlugin, Image


class GifExport:
    MAX_BYTES = 100 * 1024 * 1024

    def __init__(self, path, durations, loop=True):
        if (not isinstance(durations, list) or not 1 <= len(durations) <= 6000
                or any(type(ms) is not int or not 20 <= ms <= 655350 or ms % 10 for ms in durations)):
            raise ValueError('GIF 时长应为 20–655350 毫秒、10 毫秒的倍数，最多 6000 帧。')
        self.path = Path(path)
        self.durations = durations
        self.loop = bool(loop)
        self.count = 0
        self.size = None
        self.finished = False
        self.closed = False
        self.lock = threading.Lock()
        self.output = self.path.open('wb')

    def append(self, png, index):
        with self.lock:
            if self.closed or self.finished or index != self.count or index >= len(self.durations):
                raise ValueError('GIF 帧顺序无效，或任务已结束。')
            with Image.open(io.BytesIO(png)) as image:
                if image.format != 'PNG' or max(image.size) > 2048 or image.width * image.height > 2048 ** 2:
                    raise ValueError('GIF 帧应为不超过 2048 × 2048 的 PNG。')
                if self.size is not None and image.size != self.size:
                    raise ValueError('所有 GIF 帧必须具有相同尺寸。')
                # No dithering: keep fine glyph edges stable between frames.
                frame = image.convert('RGB').quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                                                       dither=Image.Dither.NONE)
            if self.count == 0:
                self.size = frame.size
                info = {'duration': self.durations[0]}
                if self.loop:
                    info['loop'] = 0
                header, _ = GifImagePlugin.getheader(frame, info=info)
                for block in header:
                    self.output.write(block)
            # Every frame covers the full canvas; local palettes preserve frame colors.
            for block in GifImagePlugin.getdata(frame, duration=self.durations[index], disposal=1,
                                                include_color_table=self.count > 0):
                self.output.write(block)
            if self.output.tell() > self.MAX_BYTES:
                raise ValueError('GIF 超过 100 MB，请降低尺寸、抽帧密度或缩短片段。')
            self.count += 1

    def result(self):
        with self.lock:
            if self.closed or self.count != len(self.durations):
                raise ValueError('GIF 尚未完成。')
            if not self.finished:
                self.output.write(b';')
                self.output.close()
                self.finished = True
            return self.path.read_bytes()

    def close(self):
        with self.lock:
            self.closed = True
            self.output.close()
            self.path.unlink(missing_ok=True)

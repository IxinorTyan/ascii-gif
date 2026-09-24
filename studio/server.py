"""Local-only media decoding service for Suzu ASCII Studio (no web dependencies)."""
from __future__ import annotations

import argparse
import io
import json
import math
import mimetypes
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse, parse_qs
import webbrowser

import cv2
from PIL import Image
from gif_encoder import GifExport

WEB = Path(__file__).parent / 'web'
MAX_UPLOAD = 1024 ** 3


class Media:
    def __init__(self, path, name):
        self.path = Path(path)
        self.name = name
        self.lock = threading.Lock()
        self.reader = None
        self.next_index = 0
        self.durations = []
        self.timing = '源帧率'
        with self.path.open('rb') as stream:
            self.is_gif = stream.read(6) in (b'GIF87a', b'GIF89a')
        try:
            if self.is_gif:
                self.reader = Image.open(self.path)
                width, height = self.reader.size
                for index in range(self.reader.n_frames):
                    self.reader.seek(index)
                    self.durations.append(float(self.reader.info.get('duration', 100) or 100))
                self.timing = 'GIF 原始帧时长'
            else:
                self.reader = cv2.VideoCapture(str(self.path))
                if not self.reader.isOpened():
                    raise ValueError('无法解码此文件，请尝试 MP4（H.264）、WebM、MOV 或 GIF。')
                count = int(self.reader.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = self.reader.get(cv2.CAP_PROP_FPS)
                width = int(self.reader.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(self.reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if not 0 < count <= 500000 or not math.isfinite(fps) or fps <= 0:
                    raise ValueError('无法读取有效帧数或帧率，或视频超过 50 万帧。')
                self.durations = [1000 / fps] * count
                self.read_timestamps(count)
            if width <= 0 or height <= 0 or not self.durations:
                raise ValueError('媒体没有可用画面。')
            self.starts = []
            duration = 0
            for value in self.durations:
                self.starts.append(duration)
                duration += value
            self.info = dict(name=name, kind='GIF' if self.is_gif else '视频',
                             width=width, height=height, count=len(self.durations),
                             duration=duration, starts=self.starts, durations=self.durations,
                             timing=self.timing)
        except Exception:
            self.close()
            raise

    def read_timestamps(self, count):
        """Use actual timestamps for variable-rate videos when ffprobe is installed."""
        probe = shutil.which('ffprobe')
        if not probe:
            self.timing = '平均帧率（未安装 ffprobe）'
            return
        try:
            result = subprocess.run(
                [probe, '-v', 'error', '-select_streams', 'v:0', '-show_frames',
                 '-show_entries', 'frame=best_effort_timestamp_time,duration_time,pkt_duration_time',
                 '-of', 'json', str(self.path)], capture_output=True, timeout=120,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True)
            frames = json.loads(result.stdout)['frames']
            stamps = [float(frame['best_effort_timestamp_time']) * 1000 for frame in frames]
            differences = [b - a for a, b in zip(stamps, stamps[1:])]
            last = float(frames[-1].get('duration_time', frames[-1].get('pkt_duration_time',
                         self.durations[-1] / 1000))) * 1000
            durations = differences + [last if last > 0 else self.durations[-1]]
            if len(durations) == count and all(math.isfinite(x) and x > 0 for x in durations):
                self.durations = durations
                self.timing = '源帧时间戳'
            else:
                self.timing = '平均帧率（时间戳不可用）'
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError):
            self.timing = '平均帧率（时间戳不可用）'

    def frame(self, index):
        if index < 0 or index >= len(self.durations):
            raise ValueError('帧编号超出范围。')
        with self.lock:
            if self.reader is None:
                raise ValueError('媒体已关闭，请重新导入。')
            if self.is_gif:
                self.reader.seek(index)
                image = self.reader.convert('RGBA')
            else:
                if index != self.next_index:
                    if not self.reader.set(cv2.CAP_PROP_POS_FRAMES, index):
                        raise ValueError('无法定位指定帧。')
                ok, pixels = self.reader.read()
                if not ok:
                    raise ValueError(f'第 {index + 1} 帧解码失败。')
                self.next_index = index + 1
                image = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
            output = io.BytesIO()
            image.save(output, format='PNG', compress_level=1)
            return output.getvalue()

    def close(self):
        if self.reader is not None:
            if self.is_gif:
                self.reader.close()
            else:
                self.reader.release()
            self.reader = None


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address):
        super().__init__(address, Handler)
        self.token = secrets.token_urlsafe(32)
        self.temp = tempfile.TemporaryDirectory(prefix='suzu-ascii-')
        self.media = {}
        self.media_lock = threading.Lock()
        self.gif_exports = {}

    def server_close(self):
        super().server_close()
        for media in self.media.values():
            with media.lock:
                media.close()
        self.media.clear()
        for export in self.gif_exports.values():
            export.close()
        self.gif_exports.clear()
        self.temp.cleanup()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if args and str(args[1] if len(args) > 1 else '') not in ('200', '204'):
            super().log_message(format, *args)

    def send(self, status, content, content_type='application/json; charset=utf-8'):
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False).encode('utf-8')
        elif isinstance(content, str):
            content = content.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass  # A cancelled preview/export may close its HTTP request.

    def authorized(self, api=False):
        host = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != host:
            self.send(403, {'error': '请从本机启动地址打开。'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin != f'http://{host}':
            self.send(403, {'error': '不允许跨站请求。'})
            return False
        if api and self.headers.get('X-Studio-Token') != self.server.token:
            self.send(403, {'error': '连接已失效，请刷新页面。'})
            return False
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        if not self.authorized(parsed.path.startswith('/api/')):
            return
        try:
            if parsed.path == '/api/gif':
                export = self.server.gif_exports.get(parse_qs(parsed.query).get('id', [''])[0])
                if export is None:
                    raise ValueError('GIF 导出任务不存在，请重新导出。')
                self.send(200, export.result(), 'image/gif')
            elif parsed.path == '/api/frame':
                query = parse_qs(parsed.query)
                media = self.server.media.get(query.get('id', [''])[0])
                if media is None:
                    raise ValueError('媒体已关闭，请重新导入。')
                self.send(200, media.frame(int(query.get('index', ['0'])[0])), 'image/png')
            else:
                name = 'index.html' if parsed.path == '/' else parsed.path.lstrip('/')
                path = (WEB / name).resolve()
                if not path.is_relative_to(WEB.resolve()) or not path.is_file():
                    self.send(404, {'error': '未找到页面。'})
                    return
                data = path.read_bytes()
                if name == 'index.html':
                    data = data.replace(b'__STUDIO_TOKEN__', self.server.token.encode())
                mime = {'.mjs': 'text/javascript', '.css': 'text/css', '.html': 'text/html'}.get(path.suffix,
                       mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                self.send(200, data, mime + ('; charset=utf-8' if mime.startswith('text/') else ''))
        except (ValueError, OSError, KeyError) as error:
            self.send(400, {'error': str(error)})

    def do_POST(self):
        if not self.authorized(True):
            return
        parsed = urlparse(self.path)
        if parsed.path in ('/api/gif', '/api/gif/frame'):
            try:
                if parsed.path == '/api/gif':
                    options = json.loads(self.read_body(100000))
                    with self.server.media_lock:
                        if len(self.server.gif_exports) >= 4:
                            raise ValueError('GIF 导出任务过多，请关闭其他导出页面或重启服务。')
                        export_id = secrets.token_hex(16)
                        export = GifExport(Path(self.server.temp.name) / (export_id + '.gif'),
                                           options.get('durations'), options.get('loop', True))
                        self.server.gif_exports[export_id] = export
                    self.send(200, {'id': export_id})
                else:
                    query = parse_qs(parsed.query)
                    export = self.server.gif_exports.get(query.get('id', [''])[0])
                    if export is None:
                        raise ValueError('GIF 导出任务不存在，请重新导出。')
                    export.append(self.read_body(20 * 1024 * 1024), int(query.get('index', ['-1'])[0]))
                    self.send(200, {'frames': export.count})
            except (ValueError, OSError, AttributeError) as error:
                self.send(400, {'error': str(error)})
            return
        if self.path != '/api/media':
            self.send(404, {'error': '未知操作。'})
            return
        path = None
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= MAX_UPLOAD:
                raise ValueError('请选择小于 1 GB 的非空视频或 GIF。')
            name = Path(unquote(self.headers.get('X-Filename', 'media'))).name
            media_id = secrets.token_hex(16)
            path = Path(self.server.temp.name) / (media_id + Path(name).suffix[:12])
            remaining = size
            with path.open('wb') as output:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError('文件读取中断，请重试。')
                    output.write(chunk)
                    remaining -= len(chunk)
            media = Media(path, name)
            with self.server.media_lock:
                self.server.media[media_id] = media
            self.send(200, dict(id=media_id, **media.info))
        except Exception as error:
            if path and path.exists() and not any(m.path == path for m in self.server.media.values()):
                path.unlink()
            self.send(400, {'error': str(error)})

    def read_body(self, maximum):
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= maximum:
            raise ValueError('请求数据为空或超过大小限制。')
        data = self.rfile.read(length)
        if len(data) != length:
            raise ValueError('请求数据不完整。')
        return data

    def do_DELETE(self):
        if not self.authorized(True):
            return
        if urlparse(self.path).path == '/api/gif':
            query = parse_qs(urlparse(self.path).query)
            with self.server.media_lock:
                export = self.server.gif_exports.pop(query.get('id', [''])[0], None)
            if export:
                export.close()
            self.send(200, {'ok': True})
            return
        if urlparse(self.path).path != '/api/media':
            self.send(404, {'error': '未知操作。'})
            return
        query = parse_qs(urlparse(self.path).query)
        with self.server.media_lock:
            media = self.server.media.pop(query.get('id', [''])[0], None)
        if media:
            with media.lock:
                media.close()
                media.path.unlink(missing_ok=True)
        self.send(200, {'ok': True})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    server = StudioServer(('127.0.0.1', args.port))
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'Suzu ASCII Studio: {url}', flush=True)
    print('Keep this window open. Press Ctrl+C to exit.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

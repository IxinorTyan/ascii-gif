import http.client
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Media, StudioServer


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def test_gif_disposal_and_nonuniform_timing(self):
        frames = []
        palette = [0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255] + [0] * (768 - 12)
        for index in range(3):
            frame = Image.new('P', (18, 18), 0)
            frame.putpalette(palette)
            for y in range(4):
                for x in range(4):
                    frame.putpixel((x + index * 5, y), index + 1)
            frames.append(frame)
        path = self.path / '透明.gif'
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=[40, 120, 200],
                       transparency=0, disposal=2, loop=0, optimize=False)
        media = Media(path, path.name)
        self.addCleanup(media.close)
        self.assertEqual(media.info['durations'], [40, 120, 200])
        self.assertEqual(media.info['starts'], [0, 40, 160])
        self.assertEqual(media.info['duration'], 360)
        # Forward and backward seeks must apply disposal rather than retain old patches.
        for index in [2, 0, 1, 2]:
            with Image.open(io.BytesIO(media.frame(index))) as image:
                self.assertEqual(image.getpixel((index * 5, 0))[3], 255)
                if index:
                    self.assertEqual(image.getpixel((0, 0))[3], 0)
        with self.assertRaises(ValueError):
            media.frame(3)

    def test_video_decoding_and_random_seek(self):
        path = self.path / 'sample.avi'
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 20, (32, 24))
        self.assertTrue(writer.isOpened())
        for shade in [0, 60, 130, 240]:
            writer.write(np.full((24, 32, 3), shade, np.uint8))
        writer.release()
        media = Media(path, path.name)
        self.addCleanup(media.close)
        self.assertEqual(media.info['count'], 4)
        self.assertAlmostEqual(media.info['duration'], 200, places=2)
        for index in [3, 0, 1, 3]:
            with Image.open(io.BytesIO(media.frame(index))) as image:
                self.assertAlmostEqual(np.asarray(image).mean(), [0, 60, 130, 240][index], delta=4)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = StudioServer(('127.0.0.1', 0))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        connection.close()
        return result

    def test_import_preview_release_and_local_access(self):
        status, page, _ = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(self.server.token.encode(), page)
        self.assertNotIn(b'__STUDIO_TOKEN__', page)
        headers = {'X-Studio-Token': self.server.token, 'X-Filename': 'demo.gif', 'Content-Type': 'application/octet-stream'}
        gif = (Path(__file__).resolve().parents[1] / 'web/demo.gif').read_bytes()
        self.assertEqual(self.request('POST', '/api/media', b'blocked')[0], 403)
        self.assertEqual(self.request('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('POST', '/api/media', b'blocked', dict(headers, Origin='https://evil.example'))[0], 403)
        status, body, _ = self.request('POST', '/api/media', gif, headers)
        self.assertEqual(status, 200, body)
        media = json.loads(body)
        self.assertEqual(media['count'], 36)
        status, image, response_headers = self.request('GET', f'/api/frame?id={media["id"]}&index=12', headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(Image.open(io.BytesIO(image)).size, (320, 240))
        self.assertEqual(response_headers['Content-Type'], 'image/png')
        self.assertEqual(self.request('DELETE', f'/api/media?id={media["id"]}', headers=headers)[0], 200)
        self.assertEqual(self.request('GET', f'/api/frame?id={media["id"]}&index=0', headers=headers)[0], 400)

    def test_failed_import_leaves_no_temp_file(self):
        headers = {'X-Studio-Token': self.server.token, 'X-Filename': 'broken.gif'}
        before = set(Path(self.server.temp.name).iterdir())
        self.assertEqual(self.request('POST', '/api/media', b'not a media file', headers)[0], 400)
        self.assertEqual(set(Path(self.server.temp.name).iterdir()), before)

    def test_gif_export_encoding_timing_and_cleanup(self):
        headers = {'X-Studio-Token': self.server.token, 'Content-Type': 'application/json'}
        for looping in (True, False):
            status, body, _ = self.request('POST', '/api/gif', json.dumps({
                'durations': [40, 120, 200], 'loop': looping}), headers)
            self.assertEqual(status, 200, body)
            job = json.loads(body)['id']
            path = f'/api/gif?id={job}'
            self.assertEqual(self.request('GET', path, headers=headers)[0], 400)
            for index, color in enumerate(['red', 'green', 'blue']):
                png = io.BytesIO()
                Image.new('RGB', (32, 20), color).save(png, 'PNG')
                if index == 0:
                    self.assertEqual(self.request('POST', f'/api/gif/frame?id={job}&index=1', png.getvalue(), headers)[0], 400)
                status, body, _ = self.request('POST', f'/api/gif/frame?id={job}&index={index}', png.getvalue(), headers)
                self.assertEqual(status, 200, body)
            status, gif, response_headers = self.request('GET', path, headers=headers)
            self.assertEqual(status, 200)
            self.assertTrue(gif.startswith(b'GIF89a'))
            self.assertEqual(response_headers['Content-Type'], 'image/gif')
            with Image.open(io.BytesIO(gif)) as image:
                self.assertEqual(image.n_frames, 3)
                self.assertEqual(image.size, (32, 20))
                self.assertEqual('loop' in image.info, looping)
                if looping:
                    self.assertEqual(image.info['loop'], 0)
                for index, expected in enumerate([(255, 0, 0), (0, 128, 0), (0, 0, 255)]):
                    image.seek(index)
                    self.assertEqual(image.info['duration'], [40, 120, 200][index])
                    self.assertEqual(image.convert('RGB').getpixel((0, 0)), expected)
            self.assertEqual(self.request('DELETE', path, headers=headers)[0], 200)
            self.assertFalse((Path(self.server.temp.name) / (job + '.gif')).exists())

    def test_cancel_gif_removes_partial_output_and_validates_frames(self):
        headers = {'X-Studio-Token': self.server.token}
        self.assertEqual(self.request('POST', '/api/gif', json.dumps({'durations': [1]}), headers)[0], 400)
        _, body, _ = self.request('POST', '/api/gif', json.dumps({'durations': [40, 40]}), headers)
        job = json.loads(body)['id']
        for index, size in enumerate([(32, 20), (40, 20)]):
            png = io.BytesIO()
            Image.new('RGB', size).save(png, 'PNG')
            result = self.request('POST', f'/api/gif/frame?id={job}&index={index}', png.getvalue(), headers)
            self.assertEqual(result[0], 200 if index == 0 else 400)
        self.request('DELETE', f'/api/gif?id={job}', headers=headers)
        self.assertNotIn(job, self.server.gif_exports)
        self.assertFalse((Path(self.server.temp.name) / (job + '.gif')).exists())


if __name__ == '__main__':
    unittest.main()

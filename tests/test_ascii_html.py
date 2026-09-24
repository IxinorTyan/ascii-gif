import json
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ascii_html import export_html, media_frames, media_frame_count, preview_frame, ExportCancelled


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.settings = json.loads((Path(__file__).resolve().parents[1] / 'scripts/config.json').read_text('utf-8'))
        self.gif = self.path / '动画.gif'
        images = [Image.new('RGB', (24, 18), color) for color in ['black', 'white', 'red']]
        images[0].save(self.gif, save_all=True, append_images=images[1:], duration=[40, 120, 200], loop=0)

    def test_gif_timing_range_and_real_text(self):
        output = self.path / '动画.html'
        self.settings['video_frames_interval'] = [1, 3]
        self.settings['colored_image'] = True
        self.assertEqual(export_html(self.gif, output, self.settings, (6, 9)), 2)
        html = output.read_text('utf-8')
        payload = html.split('<script id="ascii-data" type="application/json">')[1].split('</script>')[0]
        data = json.loads(payload)
        self.assertEqual([f['duration'] for f in data['frames']], [120, 200])
        self.assertEqual(data['frames'][1]['colors'], ['#ff0000'] * 8)
        self.assertEqual(len(data['frames'][0]['text'].splitlines()), 2)
        self.assertNotIn('<img', html)
        self.assertNotIn('src=', html)

    def test_video_timing_and_range(self):
        video = self.path / 'source.avi'
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 20, (24, 18))
        self.assertTrue(writer.isOpened())
        try:
            for value in [0, 80, 160, 255]:
                writer.write(np.full((18, 24, 3), value, np.uint8))
        finally:
            writer.release()
        frames = list(media_frames(video, [1, 3]))
        self.assertEqual(len(frames), 2)
        self.assertEqual([frame[1] for frame in frames], [50, 50])
        self.assertLess(np.asarray(frames[0][0]).mean(), np.asarray(frames[1][0]).mean())
        self.assertEqual(media_frame_count(video), 4)
        image, frame, duration = preview_frame(video, 2, self.settings, (6, 9))
        self.assertEqual(duration, 50)
        self.assertAlmostEqual(np.asarray(image).mean(), np.asarray(frames[1][0]).mean())

    def test_preview_matches_export_and_applies_current_settings(self):
        self.assertEqual(media_frame_count(self.gif), 3)
        self.settings['colored_image'] = True
        image, frame, duration = preview_frame(self.gif, 2, self.settings, (6, 9))
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))
        self.assertEqual(duration, 200)
        output = self.path / 'preview-match.html'
        export_html(self.gif, output, self.settings, (6, 9))
        payload = output.read_text('utf-8').split('<script id="ascii-data" type="application/json">')[1].split('</script>')[0]
        exported = json.loads(payload)['frames'][2]
        self.assertEqual(frame, {key: exported[key] for key in ('text', 'colors')})
        self.settings['resize_ratio'] = 2
        self.settings['colored_image'] = False
        _, changed, _ = preview_frame(self.gif, 2, self.settings, (6, 9))
        self.assertEqual(changed['colors'], [])
        self.assertEqual(len(changed['text']), 2)
        with self.assertRaises(ValueError):
            preview_frame(self.gif, 3, self.settings, (6, 9))

    def test_preview_window_controls(self):
        import time
        import tkinter as tk
        from ascii_preview import AsciiPreview
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        self.settings['video_frames_interval'] = [1, 3]
        preview = AsciiPreview(root, str(self.gif), lambda: (self.settings.copy(), (6, 9)))
        preview.withdraw()

        def wait_for_frame(index):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                root.update()
                if preview.status.cget('text').startswith(f'已渲染第 {index} 帧'):
                    return
                time.sleep(.01)
            self.fail(preview.status.cget('text'))

        wait_for_frame(1)
        self.assertEqual(int(preview.timeline.cget('from')), 1)
        self.assertEqual(int(preview.timeline.cget('to')), 2)
        preview.step(1)
        wait_for_frame(2)
        expected = preview_frame(self.gif, 2, self.settings, (6, 9))[1]['text']
        self.assertEqual(preview.text.get('1.0', 'end-1c'), expected)
        self.settings['colored_image'] = True
        preview.render()
        wait_for_frame(2)
        self.assertIn('#ff0000', preview.text.tag_names())
        # Closing during a decode must not run callbacks against destroyed widgets.
        preview.render()
        preview.close()
        root.update()

    def test_cancel_and_invalid_range_preserve_destination(self):
        output = self.path / 'existing.html'
        output.write_text('existing', encoding='utf-8')
        with self.assertRaises(ExportCancelled):
            export_html(self.gif, output, self.settings, (6, 9), cancelled=lambda: True)
        self.settings['video_frames_interval'] = [99, 100]
        with self.assertRaises(ValueError):
            export_html(self.gif, output, self.settings, (6, 9))
        self.assertEqual(output.read_text('utf-8'), 'existing')
        self.settings['video_frames_interval'] = [-1, 3]
        with self.assertRaises(ValueError):
            export_html(self.gif, output, self.settings, (6, 9))

    def test_custom_characters_cannot_escape_json_script(self):
        self.settings['ascii_character_set'] = '</script>&"'
        output = self.path / 'safe.html'
        export_html(self.gif, output, self.settings, (6, 9))
        payload = output.read_text('utf-8').split('<script id="ascii-data" type="application/json">')[1].split('</script>')[0]
        self.assertNotIn('<', payload)
        self.assertNotIn('&', payload)
        self.assertEqual(len(json.loads(payload)['frames']), 3)


if __name__ == '__main__':
    unittest.main()

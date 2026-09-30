import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { decodeGif } from '../media.mjs';
import { exportGif } from '../gif.mjs';
import { DEFAULTS } from '../ascii.mjs';

test('Media: decodeGif accurately parses animated demo.gif frames and durations', async () => {
  const buf = fs.readFileSync('demo.gif');
  const file = new File([buf], 'demo.gif', { type: 'image/gif' });
  const media = await decodeGif(file);

  assert.equal(media.name, 'demo.gif');
  assert.equal(media.kind, 'GIF');
  assert.equal(media.width, 320);
  assert.equal(media.height, 240);
  assert.equal(media.count, 36);
  assert.ok(media.duration > 0);
  assert.equal(media.starts.length, 36);
  assert.equal(media.durations.length, 36);

  const frame0 = media.getFrameImage(0);
  assert.ok(frame0);
  assert.equal(frame0.width, 320);
  assert.equal(frame0.height, 240);

  media.close();
});

test('GIF: exportGif generates valid GIF89a Blob with custom options', async () => {
  const sampleFrames = [
    {
      frame: { text: '@#\n .', cols: 2, rows: 2, colors: [0xff0000, 0x00ff00, 0, 0x0000ff] },
      duration: 100
    },
    {
      frame: { text: '#@\n. ', cols: 2, rows: 2, colors: [0x00ff00, 0xff0000, 0x0000ff, 0] },
      duration: 120
    }
  ];

  // Mock minimal canvas and ImageData for node environment
  const previousDocument = global.document;
  const previousImageData = global.ImageData;

  class MockImageData {
    constructor(data, width, height) {
      this.data = data || new Uint8ClampedArray(width * height * 4);
      this.width = width;
      this.height = height;
    }
  }
  global.ImageData = MockImageData;

  const mockCtx = {
    font: '',
    fillStyle: '',
    textBaseline: '',
    measureText: () => ({ width: 6, fontBoundingBoxAscent: 8, fontBoundingBoxDescent: 2 }),
    fillRect() {},
    scale() {},
    fillText() {},
    getImageData(x, y, w, h) {
      const data = new Uint8ClampedArray(w * h * 4);
      data.fill(200);
      return new MockImageData(data, w, h);
    }
  };

  global.document = {
    createElement: () => ({
      width: 0,
      height: 0,
      getContext: () => mockCtx
    })
  };

  try {
    const blob = await exportGif(sampleFrames, DEFAULTS, { loop: true, gifSize: 480 });
    assert.ok(blob);
    assert.equal(blob.type, 'image/gif');
    const bytes = new Uint8Array(await blob.arrayBuffer());
    assert.ok(bytes.length > 0);
    const header = String.fromCharCode(...bytes.slice(0, 6));
    assert.equal(header, 'GIF89a');
  } finally {
    global.document = previousDocument;
    global.ImageData = previousImageData;
  }
});

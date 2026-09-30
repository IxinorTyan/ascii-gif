import { GifReader } from './lib/omggif.mjs';

/**
 * Check if the file starts with GIF magic bytes (GIF87a / GIF89a).
 */
export async function isGifFile(file) {
  if (file.type === 'image/gif' || file.name.toLowerCase().endsWith('.gif')) {
    return true;
  }
  const slice = file.slice(0, 6);
  const buffer = await slice.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const header = String.fromCharCode(...bytes);
  return header === 'GIF87a' || header === 'GIF89a';
}

/**
 * Decode an animated GIF file completely in browser memory.
 */
export async function decodeGif(file) {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const reader = new GifReader(bytes);
  const width = reader.width;
  const height = reader.height;
  const count = reader.numFrames();

  if (count <= 0 || width <= 0 || height <= 0) {
    throw new Error('GIF 没有可用画面帧。');
  }

  const current = new Uint8ClampedArray(width * height * 4);
  let prevSnapshot = null;
  let lastInfo = null;

  const starts = [];
  const durations = [];
  const frameBitmaps = [];
  let totalDuration = 0;

  for (let i = 0; i < count; i++) {
    const info = reader.frameInfo(i);
    // GIF delay is in centiseconds (1/100s). Default to 100ms if 0 or missing.
    const delayMs = Math.max(20, (info.delay && info.delay > 0 ? info.delay : 10) * 10);
    starts.push(totalDuration);
    durations.push(delayMs);
    totalDuration += delayMs;

    // Handle previous frame's disposal
    if (lastInfo) {
      if (lastInfo.disposal === 2) {
        // Restore to background (transparent)
        for (let r = 0; r < lastInfo.height; r++) {
          const start = ((lastInfo.y + r) * width + lastInfo.x) * 4;
          current.fill(0, start, start + lastInfo.width * 4);
        }
      } else if (lastInfo.disposal === 3 && prevSnapshot) {
        // Restore to previous
        current.set(prevSnapshot);
      }
    }

    if (info.disposal === 3) {
      prevSnapshot = new Uint8ClampedArray(current);
    }

    reader.decodeAndBlitFrameRGBA(i, current);
    const NativeImageData = typeof ImageData !== 'undefined'
      ? ImageData
      : class {
          constructor(data, width, height) {
            this.data = data;
            this.width = width;
            this.height = height;
          }
        };

    const imgData = new NativeImageData(new Uint8ClampedArray(current), width, height);
    
    // In browser, createImageBitmap is available and super fast for canvas/drawing
    if (typeof createImageBitmap !== 'undefined') {
      frameBitmaps.push(await createImageBitmap(imgData));
    } else {
      frameBitmaps.push(imgData);
    }

    lastInfo = info;
  }

  function getFrameImage(index) {
    if (index < 0 || index >= count) {
      throw new Error(`帧索引超出范围: ${index} (总计 ${count} 帧)`);
    }
    return frameBitmaps[index];
  }

  function close() {
    for (const bm of frameBitmaps) {
      if (bm && typeof bm.close === 'function') {
        bm.close();
      }
    }
    frameBitmaps.length = 0;
  }

  return {
    name: file.name,
    kind: 'GIF',
    width,
    height,
    count,
    duration: totalDuration,
    starts,
    durations,
    timing: 'GIF 原始帧时长',
    getFrameImage,
    close
  };
}

/**
 * Decode a video file using browser's HTML5 Video and Offscreen Canvas.
 */
export async function decodeVideo(file) {
  const url = URL.createObjectURL(file);
  const video = document.createElement('video');
  video.preload = 'auto';
  video.muted = true;
  video.playsInline = true;
  video.src = url;

  await new Promise((resolve, reject) => {
    video.onloadedmetadata = () => resolve();
    video.onerror = () => reject(new Error('无法解码该视频，请确认浏览器支持此视频编码（推荐 MP4/H.264 或 WebM）。'));
  });

  const width = video.videoWidth;
  const height = video.videoHeight;
  const durationSec = video.duration;

  if (!Number.isFinite(durationSec) || durationSec <= 0 || width <= 0 || height <= 0) {
    URL.revokeObjectURL(url);
    throw new Error('无法读取视频画面分辨率或时长。');
  }

  // Use standard 30 FPS sampling by default
  const fps = 30;
  const totalFrames = Math.max(1, Math.min(6000, Math.round(durationSec * fps)));
  const stepMs = 1000 / fps;
  const starts = [];
  const durations = [];
  for (let i = 0; i < totalFrames; i++) {
    starts.push(i * stepMs);
    durations.push(stepMs);
  }

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });

  // LRU Frame cache to make timeline scrubbing and preview snappy
  const frameCache = new Map();
  const MAX_CACHE = 80;

  async function seekTo(timeSec) {
    return new Promise(resolve => {
      let resolved = false;
      const onSeeked = () => {
        if (!resolved) {
          resolved = true;
          video.removeEventListener('seeked', onSeeked);
          resolve();
        }
      };
      video.addEventListener('seeked', onSeeked);
      const targetTime = Math.max(0, Math.min(durationSec, timeSec));
      if (Math.abs(video.currentTime - targetTime) < 0.001) {
        resolved = true;
        video.removeEventListener('seeked', onSeeked);
        resolve();
        return;
      }
      video.currentTime = targetTime;
      // Safety timeout in case seeked doesn't fire
      setTimeout(() => {
        if (!resolved) {
          resolved = true;
          video.removeEventListener('seeked', onSeeked);
          resolve();
        }
      }, 500);
    });
  }

  async function getFrameImage(index) {
    if (index < 0 || index >= totalFrames) {
      throw new Error(`帧索引超出范围: ${index} (总计 ${totalFrames} 帧)`);
    }
    if (frameCache.has(index)) {
      return frameCache.get(index);
    }

    const timeSec = Math.min(durationSec, starts[index] / 1000);
    await seekTo(timeSec);
    ctx.drawImage(video, 0, 0, width, height);

    let bitmap;
    if (typeof createImageBitmap !== 'undefined') {
      bitmap = await createImageBitmap(canvas);
    } else {
      const copy = document.createElement('canvas');
      copy.width = width;
      copy.height = height;
      copy.getContext('2d').drawImage(canvas, 0, 0);
      bitmap = copy;
    }

    if (frameCache.size >= MAX_CACHE) {
      const firstKey = frameCache.keys().next().value;
      const oldBm = frameCache.get(firstKey);
      if (oldBm && typeof oldBm.close === 'function') {
        oldBm.close();
      }
      frameCache.delete(firstKey);
    }
    frameCache.set(index, bitmap);
    return bitmap;
  }

  function close() {
    URL.revokeObjectURL(url);
    for (const bm of frameCache.values()) {
      if (bm && typeof bm.close === 'function') {
        bm.close();
      }
    }
    frameCache.clear();
  }

  return {
    name: file.name,
    kind: '视频',
    width,
    height,
    count: totalFrames,
    duration: durationSec * 1000,
    starts,
    durations,
    timing: '浏览器解码 (~30 帧/秒)',
    getFrameImage,
    close
  };
}

/**
 * Universal media loader: automatically routes to GIF or Video decoder.
 */
export async function loadMedia(file) {
  if (await isGifFile(file)) {
    return await decodeGif(file);
  } else {
    return await decodeVideo(file);
  }
}

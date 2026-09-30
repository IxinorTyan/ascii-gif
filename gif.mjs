import { GIFEncoder, quantize, applyPalette } from './lib/gifenc.mjs';

// GIF has centisecond timing. Group very fast frames to avoid browser delay clamping.
export function gifPlan(items) {
  const grouped = [];
  let pending = null;
  for (const item of items) {
    if (!pending) pending = {...item}; else pending.duration += item.duration;
    if (pending.duration >= 20 - 1e-6) {grouped.push(pending); pending = null;}
  }
  if (pending) {
    if (grouped.length) grouped.at(-1).duration += pending.duration;
    else grouped.push(pending);
  }
  let time = 0, written = 0;
  return grouped.map(item => {
    time += item.duration;
    const duration = Math.max(20, Math.round(time / 10) * 10 - written);
    written += duration;
    if (duration > 655350) throw new Error('单帧停留时间超过 GIF 支持的范围，请缩短片段。');
    return {...item, duration};
  });
}

export function rasterizeAsciiCanvas(frame, params, maxEdge = 640) {
  const canvas = document.createElement('canvas');
  let ctx = canvas.getContext('2d');
  const font = `${params.size}px "${params.font}", monospace`;
  ctx.font = font;
  const metrics = ctx.measureText('M');
  const cellWidth = metrics.width;
  const width = Math.ceil(frame.cols * cellWidth), height = frame.rows * params.size;
  const scale = Math.min(1, maxEdge / Math.max(width, height));
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  ctx = canvas.getContext('2d');
  ctx.fillStyle = params.background; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.scale(scale, scale); ctx.font = font; ctx.textBaseline = 'alphabetic';
  const ascent = metrics.fontBoundingBoxAscent ?? params.size * .8;
  const descent = metrics.fontBoundingBoxDescent ?? params.size * .2;
  const baseline = (params.size - ascent - descent) / 2 + ascent;
  let offset = 0;
  frame.text.split('\n').forEach((line, row) => {
    if (!frame.colors.length) {
      ctx.fillStyle = params.foreground;
      ctx.fillText(line, 0, row * params.size + baseline);
    } else {
      Array.from(line).forEach((char, col) => {
        const color = frame.colors[offset++];
        if (char === ' ') return;
        ctx.fillStyle = '#' + color.toString(16).padStart(6, '0');
        ctx.fillText(char, col * cellWidth, row * params.size + baseline);
      });
    }
  });
  return canvas;
}

export function rasterizeAscii(frame, params, maxEdge = 640) {
  const canvas = rasterizeAsciiCanvas(frame, params, maxEdge);
  return new Promise((resolve, reject) => canvas.toBlob(blob => {
    if (blob) resolve(blob); else reject(new Error('字符图片渲染失败。'));
  }, 'image/png'));
}

export async function exportGif(framesWithDuration, params, options = {}, onProgress, signal) {
  const encoder = new GIFEncoder();
  const maxEdge = Number(options.gifSize) || 480;
  const total = framesWithDuration.length;

  for (let i = 0; i < total; i++) {
    if (signal?.aborted) {
      throw new DOMException('已取消导出', 'AbortError');
    }
    if (onProgress) {
      onProgress(i, total);
    }
    const item = framesWithDuration[i];
    const canvas = rasterizeAsciiCanvas(item.frame, params, maxEdge);
    const ctx = canvas.getContext('2d');
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const palette = quantize(data, 256);
    const indexStream = applyPalette(data, palette);
    encoder.writeFrame(indexStream, canvas.width, canvas.height, {
      palette,
      delay: item.duration,
      repeat: options.loop ? 0 : -1
    });
  }

  encoder.finish();
  return new Blob([encoder.bytes()], { type: 'image/gif' });
}

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

export function rasterizeAscii(frame, params, maxEdge = 640) {
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
  return new Promise((resolve, reject) => canvas.toBlob(blob => {
    if (blob) resolve(blob); else reject(new Error('字符图片渲染失败。'));
  }, 'image/png'));
}

// Adapted from SuzuVisualLab's asciiProcessor.ts (MIT; see ../LICENSE-SuzuVisualLab).
export const PRESETS = {
  default: 'M@N%W$E#RK&FXYI*l]}1/+i>"!~`:\'. ',
  simple: '@#S%?*+:;,. ', binary: '01 ', blocks: '█▓▒░ '
};
export const DEFAULTS = {
  preset: 'default', custom: '@%#*+=-:. ', invert: true, space: true,
  cols: 100, aspect: 0.5, color: false, foreground: '#dcd5ff', background: '#131319',
  font: 'Consolas', size: 10, brightness: 0, contrast: 1
};

export function dimensions(width, height, params) {
  const cols = Math.max(10, Math.min(240, Math.round(Number(params.cols))));
  const aspect = Number(params.aspect);
  if (!Number.isFinite(cols) || !Number.isFinite(aspect) || aspect < .1 || aspect > 2)
    throw new Error('字符列数或宽高比例无效。');
  const rows = Math.max(1, Math.round(cols * height / width * aspect));
  if (cols * rows > 120000) throw new Error('字符数量过多，请降低列数或高度比例。');
  return {cols, rows};
}

export function pixelsToAscii(pixels, cols, rows, params) {
  let chars = Array.from(params.preset === 'custom' ? params.custom : PRESETS[params.preset] || PRESETS.default);
  if (chars.some(char => /[\r\n\t]/.test(char))) throw new Error('字符集不能包含换行或制表符。');
  if (params.space) {if (!chars.includes(' ')) chars.push(' ');}
  else chars = chars.filter(char => char !== ' ');
  if (!chars.length) throw new Error('请至少输入一个字符。');
  if (params.invert) chars.reverse();
  const lines = [], colors = [];
  for (let row = 0; row < rows; row++) {
    let line = '';
    for (let col = 0; col < cols; col++) {
      const offset = (row * cols + col) * 4;
      let r = pixels[offset], g = pixels[offset + 1], b = pixels[offset + 2];
      const alpha = pixels[offset + 3];
      const adjust = x => Math.max(0, Math.min(255, (x - 128) * params.contrast + 128 + params.brightness));
      r = Math.round(adjust(r)); g = Math.round(adjust(g)); b = Math.round(adjust(b));
      const gray = .2126 * r + .7152 * g + .0722 * b;
      line += alpha === 0 ? ' ' : chars[Math.min(chars.length - 1, Math.floor(gray / 256 * chars.length))];
      if (params.color) colors.push((r << 16) | (g << 8) | b);
    }
    lines.push(line);
  }
  return {text: lines.join('\n'), colors, cols, rows};
}

export function convertFrame(image, params) {
  const {cols, rows} = dimensions(image.width, image.height, params);
  const canvas = document.createElement('canvas');
  canvas.width = cols; canvas.height = rows;
  const context = canvas.getContext('2d', {willReadFrequently: true});
  context.drawImage(image, 0, 0, cols, rows);
  return pixelsToAscii(context.getImageData(0, 0, cols, rows).data, cols, rows, params);
}

export function frameAt(starts, ms) {
  let lo = 0, hi = starts.length - 1;
  while (lo < hi) { const mid = Math.ceil((lo + hi) / 2); if (starts[mid] <= ms) lo = mid; else hi = mid - 1; }
  return lo;
}

export function samplePlan(media, start, end, fps) {
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end >= media.count || end < start)
    throw new Error('请选择有效的起止帧。');
  if (!Number.isFinite(fps) || fps < 0 || fps > 240) throw new Error('抽帧密度无效。');
  const selected = [start];
  if (!fps) { for (let i = start + 1; i <= end; i++) selected.push(i); }
  else {
    const step = 1000 / fps, stop = media.starts[end] + media.durations[end];
    for (let time = media.starts[start] + step; time < stop - .001; time += step) {
      const index = Math.min(end, frameAt(media.starts, time));
      if (index !== selected.at(-1)) selected.push(index);
    }
  }
  return selected.map((index, i) => ({index, duration: (i + 1 < selected.length
    ? media.starts[selected[i + 1]] : media.starts[end] + media.durations[end]) - media.starts[index]}));
}

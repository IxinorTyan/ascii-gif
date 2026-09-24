// Standalone Canvas engine: bounded glyph atlas + bounded raster-frame LRU.
export function createBackgroundRenderer(canvas, style) {
  const ctx = canvas.getContext('2d', {alpha: false});
  const measure = document.createElement('canvas').getContext('2d');
  measure.font = `${style.size}px "${style.font}", monospace`;
  const metrics = measure.measureText('M');
  const cellWidth = Math.ceil(metrics.width), cellHeight = style.size;
  const baseline = (cellHeight - (metrics.fontBoundingBoxAscent ?? cellHeight * .8)
    - (metrics.fontBoundingBoxDescent ?? cellHeight * .2)) / 2 + (metrics.fontBoundingBoxAscent ?? cellHeight * .8);
  const atlas = document.createElement('canvas'), atlasCols = 32, capacity = 2048;
  atlas.width = atlasCols * cellWidth; atlas.height = Math.ceil(capacity / atlasCols) * cellHeight;
  const glyph = atlas.getContext('2d');
  glyph.font = measure.font; glyph.textBaseline = 'alphabetic'; glyph.fillStyle = '#ffffff';
  const mask = document.createElement('canvas'), ink = mask.getContext('2d');
  const colors = document.createElement('canvas'), colorCtx = colors.getContext('2d');
  let colorPixels = null;
  const glyphs = new Map(), slots = new Array(capacity);
  let nextSlot = 0;
  const cache = new Map(), budget = 24 * 1024 * 1024;
  let bytes = 0, geometry = '';
  function clearFrames() {
    for (const item of cache.values()) {item.canvas.width = 0; item.canvas.height = 0;}
    cache.clear(); bytes = 0;
  }
  function draw(frame, index) {
    const key = `${frame.cols}:${frame.rows}`;
    const width = frame.cols * cellWidth, height = frame.rows * cellHeight;
    const scale = Math.min(1, 1280 / Math.max(width, height));
    if (key !== geometry) {
      clearFrames(); geometry = key;
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      mask.width = canvas.width; mask.height = canvas.height;
      colors.width = frame.cols; colors.height = frame.rows;
      colorPixels = colorCtx.createImageData(frame.cols, frame.rows);
    }
    const cached = cache.get(index);
    if (cached) {
      cache.delete(index); cache.set(index, cached);
      ctx.drawImage(cached.canvas, 0, 0); return;
    }
    ink.clearRect(0, 0, mask.width, mask.height);
    ink.setTransform(scale, 0, 0, scale, 0, 0);
    let row = 0, col = 0;
    for (const char of frame.text) {
      if (char === '\n') {row++; col = 0; continue;}
      if (char !== ' ') {
        // Cache only glyph shapes; apply the whole color grid in one composite pass.
        const glyphKey = char;
        let slot = glyphs.get(glyphKey);
        if (slot === undefined) {
          slot = nextSlot++ % capacity;
          if (slots[slot] !== undefined) glyphs.delete(slots[slot]);
          slots[slot] = glyphKey; glyphs.set(glyphKey, slot);
          const x = slot % atlasCols * cellWidth, y = Math.floor(slot / atlasCols) * cellHeight;
          glyph.clearRect(x, y, cellWidth, cellHeight);
          glyph.fillText(char, x, y + baseline, cellWidth);
        }
        ink.drawImage(atlas, slot % atlasCols * cellWidth, Math.floor(slot / atlasCols) * cellHeight,
          cellWidth, cellHeight, col * cellWidth, row * cellHeight, cellWidth, cellHeight);
      }
      col++;
    }
    ink.setTransform(1, 0, 0, 1, 0, 0);
    ink.globalCompositeOperation = 'source-in';
    if (frame.colors.length) {
      const pixels = colorPixels.data;
      for (let i = 0; i < frame.colors.length; i++) {
        const rgb = frame.colors[i], offset = i * 4;
        pixels[offset] = rgb >>> 16; pixels[offset + 1] = (rgb >>> 8) & 255;
        pixels[offset + 2] = rgb & 255; pixels[offset + 3] = 255;
      }
      colorCtx.putImageData(colorPixels, 0, 0);
      ink.imageSmoothingEnabled = false;
      ink.drawImage(colors, 0, 0, mask.width, mask.height);
    } else {
      ink.fillStyle = style.foreground; ink.fillRect(0, 0, mask.width, mask.height);
    }
    ink.globalCompositeOperation = 'source-over';
    ctx.fillStyle = style.background; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(mask, 0, 0);
    const size = canvas.width * canvas.height * 4;
    if (size <= budget) {
      let copy = null;
      while (bytes + size > budget && cache.size) {
        const first = cache.keys().next().value, item = cache.get(first);
        bytes -= item.size;
        if (!copy) copy = item.canvas;
        else {item.canvas.width = 0; item.canvas.height = 0;}
        cache.delete(first);
      }
      copy ||= document.createElement('canvas');
      if (copy.width !== canvas.width) copy.width = canvas.width;
      if (copy.height !== canvas.height) copy.height = canvas.height;
      copy.getContext('2d', {alpha:false}).drawImage(canvas, 0, 0);
      cache.set(index, {canvas:copy, size}); bytes += size;
    }
  }
  return {draw, clear:clearFrames};
}

export function backgroundPlayer(createRenderer) {
  async function start() {
    const element = document.getElementById('data');
    let payload = element.textContent;
    let data;
    if (element.dataset.encoding === 'gzip') {
      if (!globalThis.DecompressionStream) throw new Error('请使用新版浏览器打开。');
      const bytes = Uint8Array.from(atob(payload), char => char.charCodeAt(0));
      data = JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text());
    } else data = JSON.parse(payload);
    payload = ''; element.textContent = ''; element.remove();
    const {frames, style} = data;
    const ends = []; let total = 0;
    for (const frame of frames) {
      if (frame.colors.length) frame.colors = new Uint32Array(frame.colors);
      total += frame.duration; ends.push(total);
    }
    await document.fonts.ready;
    const renderer = createRenderer(document.getElementById('background'), style);
    document.body.style.background = style.background;
    let position = 0, previous = performance.now(), shown = -1, timer = null, stopped = false;
    function stop() {if (timer !== null) clearTimeout(timer); timer = null;}
    function tick() {
      timer = null;
      if (stopped || document.hidden) return;
      const now = performance.now();
      position = (position + Math.max(0, now - previous)) % total; previous = now;
      let lo = 0, hi = ends.length - 1;
      while (lo < hi) {const mid = (lo + hi) >> 1; if (position < ends[mid]) hi = mid; else lo = mid + 1;}
      // Slow devices skip old frames; never accumulate a catch-up queue.
      if (lo !== shown) {renderer.draw(frames[lo], lo); shown = lo;}
      const work = performance.now() - now;
      timer = setTimeout(tick, Math.max(4, 1000 / 30 - work, ends[lo] - position - work));
    }
    document.addEventListener('visibilitychange', () => {
      stop();
      if (!document.hidden) {previous = performance.now(); tick();}
    });
    window.addEventListener('pagehide', () => {stopped = true; stop(); renderer.clear();});
    window.addEventListener('pageshow', () => {if (stopped) {stopped = false; shown = -1; previous = performance.now(); tick();}});
    document.getElementById('message').remove(); tick();
  }
  start().catch(error => {
    const message = document.getElementById('message');
    if (message) message.textContent = '无法播放：' + error.message;
  });
}

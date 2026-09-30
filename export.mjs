import {renderAscii, ASCII_CSS} from './renderer.mjs';
import {createBackgroundRenderer, backgroundPlayer} from './background.mjs';

export function standalonePlayer(renderAscii) {
  const get = id => document.getElementById(id);
  async function start() {
    const dataElement = get('data');
    let payload = dataElement.textContent;
    let data;
    if (get('data').dataset.encoding === 'gzip') {
      if (!globalThis.DecompressionStream) throw new Error('请使用新版 Chrome、Edge、Firefox 或 Safari 打开此动画。');
      const bytes = Uint8Array.from(atob(payload), c => c.charCodeAt(0));
      data = JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text());
    } else data = JSON.parse(payload);
    payload = ''; dataElement.textContent = ''; dataElement.remove();
    const {frames, style} = data;
    for (const frame of frames) {
      if (frame.colors?.length) frame.colors = new Uint32Array(frame.colors);
    }
    const ends = []; let total = 0;
    for (const frame of frames) {total += frame.duration; ends.push(total);}
    let position = 0, previous = performance.now(), playing = true, shown = -1;
    let timer = null, speed = 1, lastControlTime = -Infinity;
    const embedded = !data.controls || new URLSearchParams(location.search).has('embed');
    if (embedded) document.body.classList.add('embed');
    get('seek').max = total; get('loop').checked = data.loop;
    document.body.style.background = style.background;
    function render(forceControls = false) {
      let lo = 0, hi = ends.length - 1;
      while (lo < hi) {const mid = (lo + hi) >> 1; if (position < ends[mid]) hi = mid; else lo = mid + 1;}
      if (shown !== lo) {
        const geometryChanged = renderAscii(get('ascii'), frames[lo], style);
        if (shown === -1 || geometryChanged) fit();
        shown = lo;
      }
      const now = performance.now();
      if (forceControls || (!embedded && now - lastControlTime >= 100)) {
        get('seek').value = position;
        const label = `${(position / 1000).toFixed(1)} / ${(total / 1000).toFixed(1)} 秒`;
        if (get('time').textContent !== label) get('time').textContent = label;
        lastControlTime = now;
      }
      const button = playing ? '暂停' : '播放';
      if (get('play').textContent !== button) get('play').textContent = button;
    }
    function fit() {
      const pre = get('ascii'), stage = get('stage');
      const scale = Math.min(1, stage.clientWidth / Math.max(1, pre.scrollWidth), stage.clientHeight / Math.max(1, pre.scrollHeight));
      pre.style.transform = `translate(-50%, -50%) scale(${scale})`;
    }
    function advance(now) {
      if (playing) {
        position += Math.max(0, now - previous) * speed;
        if (position >= total) {
          if (get('loop').checked) position %= total;
          else {position = total; playing = false;}
        }
      }
      previous = now;
    }
    function stopTimer() {if (timer !== null) clearTimeout(timer); timer = null;}
    function schedule() {
      stopTimer();
      if (!playing || document.hidden) return;
      // Wake at the next source-frame boundary, subtracting the cost of rendering.
      const delay = (ends[shown] - position) / speed - (performance.now() - previous);
      timer = setTimeout(tick, Math.max(4, Math.min(delay, embedded ? 2147483647 : 250)));
    }
    function tick() {
      timer = null;
      if (!playing || document.hidden) return;
      advance(performance.now()); render(!playing); schedule();
    }
    get('play').onclick = () => {
      advance(performance.now());
      if (!playing && position >= total) position = 0;
      playing = !playing; render(true); schedule();
    };
    get('seek').oninput = () => {position = Number(get('seek').value); previous = performance.now(); render(true); schedule();};
    get('restart').onclick = () => {position = 0; previous = performance.now(); playing = true; render(true); schedule();};
    get('speed').onchange = () => {advance(performance.now()); speed = Number(get('speed').value); render(true); schedule();};
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {advance(performance.now()); stopTimer();}
      else {previous = performance.now(); render(true); schedule();}
    });
    window.addEventListener('resize', fit);
    document.fonts.ready.then(fit);
    get('message').remove(); render(true); schedule();
  }
  start().catch(error => {get('message').textContent = '无法播放：' + error.message;});
}

export async function makeHtml(frames, style, options) {
  const json = JSON.stringify({frames, style, loop: options.loop, controls: options.controls});
  let payload = json.replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
  let encoding = 'json';
  if (options.compress && globalThis.CompressionStream) {
    const buffer = await new Response(new Blob([json]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer();
    const bytes = new Uint8Array(buffer); let binary = '';
    for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
    payload = btoa(binary); encoding = 'gzip';
  }
  const title = options.title.replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  if (options.mode === 'background') {
    return `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title>
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#131319}#background{position:fixed;inset:0;width:100%;height:100%;object-fit:cover;pointer-events:none}#message{position:fixed;inset:16px;color:#ddd;font:14px system-ui}</style></head><body>
<canvas id="background" aria-label="ASCII 动态背景"></canvas><div id="message">正在载入背景…</div>
<script id="data" type="application/json" data-encoding="${encoding}">${payload}</script><script>(${backgroundPlayer.toString()})(${createBackgroundRenderer.toString()});</script></body></html>`;
  }
  return `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title>
<style>*{box-sizing:border-box}body{margin:0;background:#131319;color:#eee;font:13px system-ui}#stage{height:calc(100dvh - 64px);position:relative;overflow:hidden;padding:12px}#ascii{${ASCII_CSS}position:absolute;left:50%;top:50%;transform-origin:center}#controls{height:64px;display:flex;align-items:center;justify-content:center;gap:14px;padding:12px;background:#202027;color:white}button,select{background:#35353f;color:white;border:0;border-radius:6px;padding:8px;cursor:pointer}#seek{flex:1;min-width:50px;max-width:600px;accent-color:#b9a0ff}label{white-space:nowrap}.embed #controls{display:none}.embed #stage{height:100dvh;padding:0}#message{position:absolute;top:12px;left:12px} @media(max-width:500px){#controls{gap:6px;font-size:11px}#restart{display:none}}</style></head>
<body><div id="message">正在载入字符动画…</div><main id="stage"><pre id="ascii" aria-label="ASCII 字符动画"></pre></main><footer id="controls"><button id="play">暂停</button><button id="restart">重播</button><input id="seek" type="range" aria-label="播放进度" min="0" step="1" value="0"><span id="time"></span><label><input id="loop" type="checkbox">循环</label><select id="speed" aria-label="播放速度"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></footer>
<script id="data" type="application/json" data-encoding="${encoding}">${payload}</script><script>(${standalonePlayer.toString()})(${renderAscii.toString()});</script></body></html>`;
}

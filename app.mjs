import {DEFAULTS, convertFrame, samplePlan, frameAt} from './ascii.mjs';
import {renderAscii} from './renderer.mjs';
import {makeHtml} from './export.mjs';
import {gifPlan, exportGif} from './gif.mjs';
import {loadMedia} from './media.mjs';

const $ = id => document.getElementById(id);
const state = {
  media: null, image: null, imageIndex: -1, sourceUrl: '', outputUrl: '',
  revision: 0, rendering: false, pending: false, loading: false, exporting: false,
  playing: false, playbackTimer: 0, frame: null, abort: null
};
const paramIds = Object.keys(DEFAULTS);
let debounce = 0;

function settings() {
  return Object.fromEntries(paramIds.map(id => {
    const element = $(id);
    return [id, element.type === 'checkbox' ? element.checked : element.type === 'range' ? Number(element.value) : element.value];
  }));
}

function status(text, error = false) {
  $('status').textContent = text;
  $('status').classList.toggle('error', error);
}

function controls() {
  const busy = state.loading || state.exporting, missing = !state.media;
  for (const id of ['previous', 'next', 'play', 'render', 'export', 'gifExport', 'frame', 'start', 'end', 'markStart', 'markEnd'])
    $(id).disabled = busy || missing;
  for (const id of [...paramIds, 'fps', 'loop', 'compress', 'controls', 'choose', 'demo', 'reset', 'gifSize', 'htmlMode', 'backgroundPreset']) $(id).disabled = busy;
  $('controls').disabled = busy || $('htmlMode').value === 'background';
  $('controls').parentElement.classList.toggle('hidden', $('htmlMode').value === 'background');
  $('modeHint').hidden = $('htmlMode').value !== 'background';
  $('backgroundPreset').hidden = $('htmlMode').value !== 'background';
  $('export').textContent = $('htmlMode').value === 'background' ? '导出流畅背景 HTML ↗' : '导出字符动画 HTML ↗';
  $('custom').disabled = busy || $('preset').value !== 'custom';
  $('foreground').disabled = busy || $('color').checked;
}

function updateOutputs() {
  for (const id of ['cols', 'aspect', 'brightness', 'contrast', 'size'])
    $(id + 'Value').textContent = ['aspect', 'contrast'].includes(id) ? Number($(id).value).toFixed(2) : $(id).value;
  controls();
}

function fitPreview() {
  if (!state.frame) return;
  const pre = $('ascii'), viewport = $('asciiViewport'), sizer = $('asciiSizer');
  const width = pre.scrollWidth, height = pre.scrollHeight;
  const scale = $('fit').checked ? Math.min(1, (viewport.clientWidth - 32) / Math.max(1, width),
    (viewport.clientHeight - 32) / Math.max(1, height)) : 1;
  pre.style.transform = `scale(${Math.max(.01, scale)})`;
  sizer.style.width = `${width * scale}px`; sizer.style.height = `${height * scale}px`;
}

function stopPlayback() {
  state.playing = false; clearTimeout(state.playbackTimer); $('play').textContent = '播放预览';
}

function frameLabel(index) {
  if (!state.media) return;
  $('frameLabel').textContent = `第 ${index} 帧 / ${state.media.count - 1}`;
  $('durationLabel').textContent = `${(state.media.starts[index] / 1000).toFixed(2)} 秒 · 本帧 ${state.media.durations[index].toFixed(1)} ms`;
}

function requestPreview(immediate = false) {
  if (!state.media || state.exporting) return;
  state.revision++; state.pending = true;
  clearTimeout(debounce);
  if (immediate) renderPending(); else debounce = setTimeout(renderPending, 100);
}

async function renderPending() {
  if (state.rendering || !state.pending || !state.media || state.exporting) return;
  state.rendering = true; state.pending = false;
  const revision = state.revision, media = state.media, index = Number($('frame').value), params = settings();
  $('renderState').textContent = `正在渲染第 ${index} 帧…`;
  try {
    if (state.imageIndex !== index || !state.image) {
      const image = await media.getFrameImage(index);
      if (revision !== state.revision) return;
      state.image = image;
      state.imageIndex = index;

      const canvas = document.createElement('canvas');
      canvas.width = image.width;
      canvas.height = image.height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(image, 0, 0);
      canvas.toBlob(blob => {
        if (revision !== state.revision || !blob) return;
        if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
        state.sourceUrl = URL.createObjectURL(blob);
        $('original').src = state.sourceUrl;
      });
    }
    if (revision !== state.revision) return;
    state.frame = convertFrame(state.image, params);
    renderAscii($('ascii'), state.frame, params);
    $('original').hidden = false; $('originalEmpty').hidden = true; $('asciiEmpty').hidden = true;
    $('asciiViewport').style.backgroundColor = params.background;
    $('gridInfo').textContent = `${state.frame.cols} × ${state.frame.rows}`;
    $('renderState').textContent = `已渲染第 ${index} 帧`;
    frameLabel(index); fitPreview();
  } catch (error) {
    if (revision === state.revision) {status(error.message, true); $('renderState').textContent = '预览失败'; stopPlayback();}
  } finally {
    state.rendering = false;
    if (state.pending) renderPending();
  }
}

function clearMedia() {
  stopPlayback(); state.revision++; state.pending = false; clearTimeout(debounce);
  if (state.media) {
    state.media.close?.();
    state.media = null;
  }
  if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
  state.image = null; state.sourceUrl = ''; state.imageIndex = -1; state.frame = null;
  if (state.outputUrl) URL.revokeObjectURL(state.outputUrl);
  state.outputUrl = ''; $('result').classList.add('hidden');
  $('gifResult').hidden = true; $('gifResult').removeAttribute('src');
  $('drop').classList.remove('hidden'); $('mediaInfo').classList.add('hidden'); $('timeline').classList.add('hidden');
  $('original').removeAttribute('src'); $('original').hidden = true;
  $('originalEmpty').hidden = false; $('asciiEmpty').hidden = false;
  $('ascii').textContent = ''; $('asciiSizer').removeAttribute('style'); $('gridInfo').textContent = '';
  $('renderState').textContent = '等待导入'; $('file').value = '';
  controls(); updatePlan();
}

async function load(file) {
  if (!file || state.loading || state.exporting) return;
  if (!file.size || file.size > 1024 ** 3) {status('请选择小于 1 GB 的非空文件。', true); return;}
  clearMedia(); state.loading = true; controls(); status('正在本地解析媒体并建立时间轴…');
  try {
    const media = await loadMedia(file);
    state.media = media;
    $('drop').classList.add('hidden'); $('mediaInfo').classList.remove('hidden');
    $('mediaInfo').textContent = `${media.name} · ${media.kind} · ${media.width} × ${media.height} · ${media.count} 帧 · ${(media.duration / 1000).toFixed(2)} 秒\n${media.timing}`;
    $('timeline').classList.remove('hidden');
    for (const id of ['frame', 'start', 'end']) $(id).max = media.count - 1;
    $('frame').value = 0; $('start').value = 0; $('end').value = media.count - 1;
    $('fps').value = 'source';
    status('拖动时间轴选帧，调整参数后会自动更新。播放预览可检查动态效果。');
    updatePlan(); requestPreview(true);
  } catch (error) {status('导入失败：' + error.message, true);}
  finally {state.loading = false; controls();}
}

function plan(background = false) {
  if ($('start').value === '' || $('end').value === '') throw new Error('请填写起止帧。');
  const fps = $('fps').value === 'source' ? 0 : Number($('fps').value);
  return samplePlan(state.media, Number($('start').value), Number($('end').value),
    background ? Math.min(30, fps || 30) : fps);
}

function updatePlan() {
  if (!state.media) {$('planInfo').textContent = '导入后可选择片段和抽帧密度。'; return;}
  try {
    const background = $('htmlMode').value === 'background', items = plan(background);
    $('planInfo').textContent = `${background ? '背景 HTML' : 'HTML'}：${items.length} 帧 · ${(items.reduce((sum, f) => sum + f.duration, 0) / 1000).toFixed(2)} 秒。抽帧保持片段总时长；GIF 使用上方抽帧设置。`;
  } catch (error) {$('planInfo').textContent = error.message;}
}

function togglePlayback() {
  if (state.playing) {stopPlayback(); return;}
  if (!state.media || state.exporting) return;
  let items;
  try {items = plan();} catch (error) {status(error.message, true); return;}
  const start = items[0].index, end = Number($('end').value), media = state.media;
  const from = media.starts[start], to = media.starts[end] + media.durations[end];
  let index = Number($('frame').value);
  if (index < start || index >= end) index = start;
  const anchor = performance.now() - (media.starts[index] - from);
  state.playing = true; $('play').textContent = '暂停预览';
  function tick() {
    if (!state.playing || !state.media) return;
    const time = from + (performance.now() - anchor) % (to - from);
    const next = Math.min(end, frameAt(media.starts, time));
    if (!state.rendering && !state.pending && next !== Number($('frame').value)) {
      $('frame').value = next; frameLabel(next); requestPreview(true);
    }
    state.playbackTimer = setTimeout(tick, 30);
  }
  $('frame').value = index; requestPreview(true); tick();
}

async function exportAnimation(format = 'html') {
  if (!state.media || state.exporting) return;
  let items;
  const background = format === 'html' && $('htmlMode').value === 'background';
  try {
    items = format === 'gif' ? gifPlan(plan()) : plan(background);
    if (items.length > 6000) throw new Error(`片段包含 ${items.length} 帧，请缩短范围或降低抽帧密度（上限 6000 帧）。`);
  } catch (error) {status(error.message, true); return;}

  stopPlayback(); state.revision++; state.pending = false;
  state.exporting = true; state.abort = new AbortController(); controls();
  $('cancel').classList.remove('hidden'); $('cancel').disabled = false;
  $('progress').classList.remove('hidden'); $('progress').value = 0;

  const media = state.media, params = settings(), signal = state.abort.signal;
  const options = {
    title: `ASCII · ${media.name}`, mode: background ? 'background' : 'text',
    loop: background || $('loop').checked, controls: !background && $('controls').checked,
    compress: $('compress').checked, gifSize: Number($('gifSize').value)
  };
  const started = performance.now();

  try {
    await document.fonts.ready;
    const framesWithDuration = [];
    let dataSize = 0;

    for (let i = 0; i < items.length; i++) {
      signal.throwIfAborted();
      const item = items[i]; status(`正在本地转换 ${i + 1} / ${items.length} 帧…`);
      const image = await media.getFrameImage(item.index);
      const frame = {...convertFrame(image, params), duration: item.duration};
      framesWithDuration.push({frame, duration: item.duration});

      if (format === 'html') {
        dataSize += JSON.stringify(frame).length * 2;
        if (dataSize > 120 * 1024 * 1024) throw new Error('字符数据超过 120 MB，请降低列数、抽帧密度或缩短片段。');
      }
      $('progress').value = (i + 1) / items.length * (format === 'gif' ? 0.5 : 0.9);
      await new Promise(resolve => setTimeout(resolve, 0));
    }

    signal.throwIfAborted();
    let blob;
    if (format === 'gif') {
      status('正在本地编码 GIF 图片…');
      blob = await exportGif(
        framesWithDuration,
        params,
        options,
        (idx, total) => {
          $('progress').value = 0.5 + (idx + 1) / total * 0.45;
          status(`正在写入 GIF 帧: ${idx + 1} / ${total}…`);
        },
        signal
      );
    } else {
      status('正在封装独立 HTML…');
      const frames = framesWithDuration.map(x => x.frame);
      blob = new Blob([await makeHtml(frames, params, options)], {type: 'text/html;charset=utf-8'});
    }

    signal.throwIfAborted();
    if (state.outputUrl) URL.revokeObjectURL(state.outputUrl);
    state.outputUrl = URL.createObjectURL(blob);
    const filename = `ascii_${media.name.replace(/\.[^.]+$/, '')}.${format}`;
    $('download').href = state.outputUrl; $('download').download = filename;
    $('download').textContent = `再次下载 ${format.toUpperCase()}`;
    $('openResult').href = state.outputUrl; $('result').classList.remove('hidden');
    $('gifResult').hidden = format !== 'gif';
    if (format === 'gif') $('gifResult').src = state.outputUrl;
    else $('gifResult').removeAttribute('src');

    $('resultHint').textContent = format === 'gif'
      ? `GIF 图片可直接放入网页的 <img> 标签。尺寸上限 ${$('gifSize').value} 像素，时长按 10 毫秒精度保存，超短帧已合并。`
      : background ? '流畅背景 HTML：自动循环、无控件，可直接作为页面或通过 iframe 嵌入。Canvas 显示字符效果，不可选择复制字符。'
      : '网页嵌入：使用 iframe 加载导出文件，在地址后加 ?embed=1 可隐藏控件。';

    $('progress').value = 1; $('download').click();
    const size = blob.size < 1024 * 1024 ? `${(blob.size / 1024).toFixed(1)} KB` : `${(blob.size / 1024 / 1024).toFixed(2)} MB`;
    status(`已导出 ${format.toUpperCase()} · ${items.length} 帧 · ${size} · 耗时 ${((performance.now() - started) / 1000).toFixed(1)} 秒。可点击下方链接预览或再次下载。`);
  } catch (error) {
    status(signal.aborted ? '已取消导出，没有生成新文件。' : '导出失败：' + error.message, !signal.aborted);
  } finally {
    state.exporting = false; $('cancel').classList.add('hidden'); $('progress').classList.add('hidden'); controls();
  }
}

for (const id of paramIds) $(id).addEventListener('input', () => {stopPlayback(); updateOutputs(); requestPreview();});
$('choose').onclick = () => $('file').click();
$('file').onchange = event => load(event.target.files[0]);
$('demo').onclick = async () => {
  try {
    status('正在载入示例动画…');
    const response = await fetch('./demo.gif');
    if (!response.ok) throw new Error('示例文件读取失败。');
    await load(new File([await response.blob()], 'demo.gif', {type: 'image/gif'}));
  } catch (error) {status(error.message, true);}
};
$('drop').ondragover = event => {event.preventDefault(); $('drop').classList.add('drag');};
$('drop').ondragleave = () => $('drop').classList.remove('drag');
$('drop').ondrop = event => {event.preventDefault(); $('drop').classList.remove('drag'); load(event.dataTransfer.files[0]);};
window.addEventListener('dragover', event => event.preventDefault());
window.addEventListener('drop', event => event.preventDefault());
$('frame').oninput = () => {stopPlayback(); frameLabel(Number($('frame').value)); requestPreview();};
$('render').onclick = () => {stopPlayback(); requestPreview(true);};
$('play').onclick = togglePlayback;
for (const [id, step] of [['previous', -1], ['next', 1]]) $(id).onclick = () => {
  stopPlayback(); $('frame').value = Math.max(0, Math.min(state.media.count - 1, Number($('frame').value) + step)); requestPreview(true);
};
for (const id of ['start', 'end', 'fps']) $(id).oninput = () => {stopPlayback(); updatePlan();};
$('markStart').onclick = () => {$('start').value = $('frame').value; updatePlan();};
$('markEnd').onclick = () => {$('end').value = $('frame').value; updatePlan();};
$('fit').onchange = fitPreview;
new ResizeObserver(fitPreview).observe($('asciiViewport'));
document.fonts.ready.then(fitPreview);
$('export').onclick = () => exportAnimation('html');
$('gifExport').onclick = () => exportAnimation('gif');
$('htmlMode').onchange = () => {controls(); updatePlan();};
$('backgroundPreset').onclick = () => {
  stopPlayback(); $('cols').value = '80'; $('fps').value = '24';
  updateOutputs(); updatePlan(); requestPreview(true);
};
$('cancel').onclick = () => {state.abort.abort(); $('cancel').disabled = true; status('正在取消…');};
$('reset').onclick = () => {clearMedia(); $('result').classList.add('hidden'); status('请选择新的媒体文件，字符设置会保留。');};
window.addEventListener('pagehide', () => {
  if (state.media) state.media.close?.();
});
updateOutputs();

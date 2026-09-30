import test from 'node:test';
import assert from 'node:assert/strict';
import {gunzipSync} from 'node:zlib';
import {DEFAULTS, pixelsToAscii, samplePlan, frameAt, dimensions} from '../ascii.mjs';
import {makeHtml, standalonePlayer} from '../export.mjs';
import {renderAscii} from '../renderer.mjs';
import {gifPlan, rasterizeAscii} from '../gif.mjs';
import {playerDom} from './player_dom.mjs';

test('GIF groups sub-20ms frames and rounds timing without accumulating drift', () => {
  const source = Array.from({length:60}, (_,index) => ({index,duration:1000/60}));
  const result = gifPlan(source);
  assert.equal(result.length,30);
  assert.equal(result.reduce((sum,frame)=>sum+frame.duration,0),1000);
  assert.ok(result.every(frame=>frame.duration>=20 && frame.duration%10===0));
  assert.deepEqual(gifPlan([{index:0,duration:40},{index:1,duration:120},{index:2,duration:200}]),
    [{index:0,duration:40},{index:1,duration:120},{index:2,duration:200}]);
  assert.deepEqual(gifPlan([{index:0,duration:25},{index:1,duration:5}]),[{index:0,duration:30}]);
});

test('GIF rasterizer draws ASCII glyphs, colors and scales longest edge', async () => {
  const previous=global.document, drawn=[];
  const ctx={measureText:()=>({width:6,fontBoundingBoxAscent:8,fontBoundingBoxDescent:2}),
    fillRect(){},scale(x,y){drawn.push(['scale',x,y]);},
    fillText(char,x,y){drawn.push([char,x,y,this.fillStyle]);}};
  const canvas={getContext:()=>ctx,toBlob:fn=>fn(new Blob(['png']))};
  global.document={createElement:()=>canvas};
  try {
    await rasterizeAscii({text:'@#\n .',cols:2,rows:2,colors:[0xff0000,0x00ff00,0,0x0000ff]},DEFAULTS,10);
    assert.equal(canvas.width,6);assert.equal(canvas.height,10);
    assert.deepEqual(drawn,[['scale',.5,.5],['@',0,8,'#ff0000'],['#',6,8,'#00ff00'],['.',6,18,'#0000ff']]);
  } finally {global.document=previous;}
});

test('Suzu luminance mapping, inversion, transparency, and Unicode charsets', () => {
  const pixels = new Uint8ClampedArray([0,0,0,255, 255,255,255,255, 255,0,0,0]);
  const params = {...DEFAULTS, preset:'custom', custom:'█░', space:true, color:true, invert:false};
  assert.equal(pixelsToAscii(pixels,3,1,params).text, '█  ');
  assert.equal(pixelsToAscii(pixels,3,1,{...params,invert:true}).text, ' █ ');
  assert.deepEqual(pixelsToAscii(pixels,3,1,params).colors, [0,0xffffff,0xff0000]);
  assert.equal(pixelsToAscii(pixels,3,1,{...params,custom:'😀',space:false}).text, '😀😀 ');
  assert.throws(() => pixelsToAscii(pixels,3,1,{...params,custom:'\n'}));
  assert.deepEqual(dimensions(320,240,DEFAULTS), {cols:100,rows:38});
});

test('Frame ranges and sampling preserve exact variable frame durations', () => {
  const media = {count:4, starts:[0,40,160,360], durations:[40,120,200,80]};
  assert.deepEqual(samplePlan(media,1,2,0), [{index:1,duration:120},{index:2,duration:200}]);
  const sampled = samplePlan(media,0,3,5);
  assert.equal(sampled.reduce((s,x) => s+x.duration,0), 440);
  assert.deepEqual(sampled.map(x=>x.index), [0,2,3]);
  assert.equal(frameAt(media.starts,159),1);
  assert.equal(frameAt(media.starts,160),2);
  assert.throws(() => samplePlan(media,3,1,0));
  assert.throws(() => samplePlan(media,0,4,0));
});

test('Standalone export supports plain/compressed data and escapes custom text', async () => {
  const frames = [{text:'</script><img src=x>\n😀',colors:[],duration:40}];
  for (const compress of [false,true]) {
    const html = await makeHtml(frames, DEFAULTS, {title:'<Suzu>',loop:true,controls:false,compress});
    const match = html.match(/data-encoding="(.*?)">(.*?)<\/script>/s);
    const payload = match[1] === 'gzip' ? gunzipSync(Buffer.from(match[2],'base64')).toString() : match[2];
    assert.deepEqual(JSON.parse(payload).frames,frames);
    assert.ok(html.includes('<title>&lt;Suzu&gt;</title>'));
    assert.ok(!html.includes('<img src=x>'));
    assert.equal((html.match(/<script/g)||[]).length,2);
    assert.ok(!html.includes('src="http'));
  }
});

test('Shared text renderer never treats characters as markup', () => {
  const dom=playerDom({});const restore=dom.install();
  try {
    const pre = dom.element();
    renderAscii(pre,{text:'<\n&😀',colors:[0xff0000,0,0xffffff]},DEFAULTS);
    assert.equal(pre.textContent,'<\n&😀');
    assert.equal(pre.children[0].style.color,'#ff0000');
    const created=dom.counts.elements;
    renderAscii(pre,{text:'>\n😀&',colors:[0,0xffffff,0]},DEFAULTS);
    assert.equal(pre.textContent,'>\n😀&');
    assert.equal(dom.counts.elements,created);
  } finally {restore();}
});

test('Standalone player pause, seek, looping, end/restart, and embedding', async () => {
  const dom=playerDom({frames:[{text:'A',colors:[],duration:40},{text:'B',colors:[],duration:120}],style:DEFAULTS,loop:true,controls:false});
  const restore=dom.install(),get=dom.get;
  try {
    standalonePlayer(renderAscii);
    await Promise.resolve();
    assert.equal(get('ascii').textContent,'A');assert.equal(dom.embedded,true);
    assert.equal(get('data').textContent,'');assert.equal(get('data').removed,true);
    dom.elapse(50);assert.equal(get('ascii').textContent,'B');
    get('play').onclick();assert.equal(get('play').textContent,'播放');
    assert.equal(dom.timers.size,0);
    get('seek').value=159;get('seek').oninput();assert.equal(get('ascii').textContent,'B');
    get('loop').checked=false;get('play').onclick();dom.elapse(1000);
    assert.equal(get('play').textContent,'播放');assert.equal(get('seek').value,160);
    assert.equal(dom.timers.size,0);
    get('restart').onclick();assert.equal(get('seek').value,0);
    get('loop').checked=true;
    get('speed').value=2;get('speed').onchange();dom.elapse(20);
    assert.equal(get('ascii').textContent,'B');
    dom.document.hidden=true;dom.events.get('visibilitychange')();
    assert.equal(dom.timers.size,0);
    dom.elapse(60000);
    dom.document.hidden=false;dom.events.get('visibilitychange')();
    assert.equal(get('ascii').textContent,'B');assert.equal(dom.timers.size,1);
  } finally {restore();}
});

test('Ten minutes of 25-FPS colored playback keeps DOM nodes and layout reads bounded', async () => {
  const frames=Array.from({length:10},(_,i)=>({
    text:Array.from({length:20},()=>((i%2?'@#':'<&').repeat(20))).join('\n'),
    colors:Array.from({length:800},(_,n)=>(n*12345+i*54321)&0xffffff),duration:40}));
  const dom=playerDom({frames,style:DEFAULTS,loop:true,controls:true});
  const restore=dom.install();
  try {
    standalonePlayer(renderAscii);await Promise.resolve();
    dom.elapse(1000);
    const baseline={...dom.counts};
    const cells=[...dom.get('ascii').children];
    dom.elapse(600000);
    assert.equal(dom.counts.elements,baseline.elements);
    assert.equal(dom.counts.replacements,baseline.replacements);
    assert.equal(dom.counts.layoutReads,baseline.layoutReads);
    assert.ok(dom.get('ascii').children.every((node,i)=>node===cells[i]));
    assert.equal(dom.timers.size,1);
    dom.get('play').onclick();const paused={...dom.counts};
    dom.elapse(60000);assert.deepEqual(dom.counts,paused);assert.equal(dom.timers.size,0);
  } finally {restore();}
});

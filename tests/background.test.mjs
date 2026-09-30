import test from 'node:test';
import assert from 'node:assert/strict';
import {createBackgroundRenderer, backgroundPlayer} from '../background.mjs';
import {makeHtml} from '../export.mjs';
import {DEFAULTS} from '../ascii.mjs';
import {playerDom} from './player_dom.mjs';

test('Canvas reuses glyphs, caches frames, and reuses evicted raster surfaces within its budget', () => {
  const previous=global.document, canvases=[];
  let shaped=0,blits=0;
  const context=()=>({font:'',measureText:()=>({width:6,fontBoundingBoxAscent:8,fontBoundingBoxDescent:2}),
    fillText(){shaped++;},drawImage(){blits++;},clearRect(){},setTransform(){},fillRect(){},
    createImageData:(w,h)=>({data:new Uint8ClampedArray(w*h*4)}),putImageData(){}});
  const create=()=>{const ctx=context(),canvas={width:0,height:0,getContext:()=>ctx};canvases.push(canvas);return canvas;};
  global.document={createElement:create};
  try {
    const canvas=create(),renderer=createBackgroundRenderer(canvas,DEFAULTS);
    const frame={text:('@#'.repeat(100)+'\n').repeat(79)+'@#'.repeat(100),colors:[],cols:200,rows:80};
    renderer.draw(frame,0);
    assert.equal(shaped,2);
    const count=blits;
    renderer.draw(frame,0);assert.equal(blits,count+1);assert.equal(shaped,2);
    for(let i=1;i<20;i++)renderer.draw(frame,i);
    const plateau=canvases.length;
    for(let i=20;i<300;i++)renderer.draw(frame,i);
    assert.equal(canvases.length,plateau);
    // Main canvas + glyph atlas + <=24 MiB cached rasters. The measure canvas is tiny.
    const bytes=canvases.reduce((sum,c)=>sum+c.width*c.height*4,0);
    assert.ok(bytes<=24*1024*1024+canvas.width*canvas.height*8+2048*6*10*4+200*80*4);
    assert.equal(shaped,2);
    renderer.clear();
    assert.equal(canvases.filter(c=>c.width===canvas.width&&c.height===canvas.height).length,2);
  } finally {global.document=previous;}
});

test('Background loops with one timer for ten minutes; stops hidden, releases cache on pagehide', async () => {
  const dom=playerDom({frames:Array.from({length:60},()=>({text:'@',cols:1,rows:1,colors:[],duration:1000/30})),style:DEFAULTS});
  const restore=dom.install();let draws=0,clears=0;
  try {
    backgroundPlayer(()=>({draw(){draws++;},clear(){clears++;}}));
    await Promise.resolve();
    dom.elapse(600000);
    assert.ok(draws>15000&&draws<=18001);
    assert.equal(dom.timers.size,1);
    dom.document.hidden=true;dom.events.get('visibilitychange')();
    const before=draws;dom.elapse(60000);assert.equal(draws,before);assert.equal(dom.timers.size,0);
    dom.document.hidden=false;dom.events.get('visibilitychange')();assert.equal(dom.timers.size,1);
    dom.events.get('pagehide')();assert.equal(clears,1);assert.equal(dom.timers.size,0);
    dom.events.get('pageshow')();assert.equal(dom.timers.size,1);
  } finally {restore();}
});

test('Exported background is standalone canvas with no progress bar or player controls', async () => {
  const html=await makeHtml([{text:'@',colors:[],cols:1,rows:1,duration:40}],DEFAULTS,
    {mode:'background',title:'背景',compress:false,loop:true,controls:false});
  assert.ok(html.includes('<canvas id="background"'));
  assert.ok(!html.includes('<pre'));
  assert.ok(!html.includes('<button'));
  assert.ok(!html.includes('type="range"'));
  assert.ok(html.includes('object-fit:cover'));
});

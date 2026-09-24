// Exercise the actual player script with a deterministic animation clock.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, '../scripts/ascii_player.html'), 'utf8');
const script = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
const data = {frames: [
  {text: '<&', colors: [], duration: 40},
  {text: 'B\nC', colors: ['#ff0000', '#00ff00'], duration: 120},
  {text: 'D', colors: [], duration: 200}
], foreground: '#000000', background: '#ffffff'};
const elements = new Map();
function element() {
  return {value: '', checked: true, textContent: '', style: {setProperty() {}},
    children: [], append(child) {this.children.push(child);},
    replaceChildren(child) {this.children = child.children;}};
}
function get(id) {if (!elements.has(id)) elements.set(id, element()); return elements.get(id);}
get('ascii-data').textContent = JSON.stringify(data);
get('speed').value = '1';
let now = 0, tick, embedded = false;
vm.runInNewContext(script, {
  document: {getElementById: get, createElement: element, createDocumentFragment: element,
    createTextNode: text => ({textContent: text}), documentElement: element(),
    body: {classList: {add: () => {embedded = true;}}}},
  performance: {now: () => now}, requestAnimationFrame: callback => {tick = callback;},
  URLSearchParams, location: {search: '?embed=1'}
});
function advance(ms) {now = ms; tick(now);}
assert.equal(embedded, true);
assert.equal(get('ascii').textContent, '<&');
advance(40);
assert.equal(get('ascii').children.map(x => x.textContent).join(''), 'B\nC');
assert.equal(get('ascii').children[0].style.color, '#ff0000');
advance(160);
assert.equal(get('ascii').textContent, 'D');
get('toggle').onclick();
advance(200);
assert.equal(get('seek').value, 160);
get('seek').value = '0'; get('seek').oninput();
get('speed').value = '2'; get('toggle').onclick();
advance(220);
assert.equal(get('seek').value, 40);
get('loop').checked = false;
advance(500);
assert.equal(get('seek').value, 360);
assert.equal(get('toggle').textContent, '播放');
get('toggle').onclick();
assert.equal(get('seek').value, 0);
get('loop').checked = true;
advance(700);
assert.equal(get('seek').value, 40);
console.log('Player checks passed: frame timing, colors, pause, seek, speed, end, restart, loop, embed.');

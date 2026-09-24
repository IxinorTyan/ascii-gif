// Shared text renderer. Keep one bounded grid; update text/color in place.
// Self-contained because this function is embedded into standalone exports.
export function renderAscii(pre, frame, style) {
  const cache = renderAscii.cache || (renderAscii.cache = new WeakMap());
  let state = cache.get(pre);
  if (!state) {state = {style: {}, shape: null, cells: []}; cache.set(pre, state);}
  const properties = {color: style.foreground, backgroundColor: style.background,
    fontFamily: `"${style.font}", monospace`, fontSize: `${style.size}px`};
  let layoutChanged = false;
  for (const [key, value] of Object.entries(properties)) {
    if (state.style[key] !== value) {
      pre.style[key] = value; state.style[key] = value;
      if (key === 'fontFamily' || key === 'fontSize') layoutChanged = true;
    }
  }
  const lines = frame.text.split('\n');
  const shape = lines.map(line => Array.from(line).length).join(',');
  const colored = !!frame.colors.length;
  if (state.shape !== shape || state.colored !== colored) {
    state.shape = shape; state.colored = colored; state.cells = [];
    if (!colored) {
      state.text = document.createTextNode('');
      pre.replaceChildren(state.text);
    } else {
      const fragment = document.createDocumentFragment();
      for (const char of frame.text) {
        if (char === '\n') {fragment.append(document.createTextNode('\n')); continue;}
        const element = document.createElement('span'), text = document.createTextNode(char);
        element.append(text); fragment.append(element);
        state.cells.push({element, text, color: -1});
      }
      pre.replaceChildren(fragment);
    }
    layoutChanged = true;
  }
  if (!colored) {
    if (state.text.data !== frame.text) state.text.data = frame.text;
  } else {
    let index = 0;
    for (const char of frame.text) {
      if (char === '\n') continue;
      const cell = state.cells[index], color = frame.colors[index++];
      if (cell.text.data !== char) cell.text.data = char;
      if (cell.color !== color) {
        cell.element.style.color = '#' + color.toString(16).padStart(6, '0');
        cell.color = color;
      }
    }
  }
  return layoutChanged;
}

export const ASCII_CSS = 'margin:0;padding:0;white-space:pre;line-height:1;letter-spacing:0;font-weight:400;font-variant-ligatures:none;font-style:normal;width:max-content;';

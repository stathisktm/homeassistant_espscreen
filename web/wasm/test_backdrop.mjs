// A page's own background picture (firmware 0.65.0, app 0.4.109): the actual firmware asks for page:<index> as the
// owner `page`, takes the app's answer to that question, decodes the picture and shows it behind the whole glass; a
// page without one shows none, and an answer to another page's question goes to that page alone.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import createModule from '../src/wasm/firmware_preview.js';

const m = await createModule({ wasmBinary: readFileSync(new URL('../src/wasm/firmware_preview.wasm', import.meta.url)) });
const width = Number(process.env.PREVIEW_WIDTH || 480), height = Number(process.env.PREVIEW_HEIGHT || 480);
assert.equal(m._preview_init(width, height, Number(process.env.PREVIEW_DPI || 170), 2, 3), 1);
let ms = 0;
function tick(n = 300) { ms += n; m._preview_time(ms, 1789401840, 0); m._preview_render(); }
const diagnostics = () => JSON.parse(m.ccall('preview_diagnostics', 'string', [], []));
const nextAction = () => m.ccall('preview_next_action', 'string', [], []);
const nextImage = () => JSON.parse(m.ccall('preview_next_image', 'string', [], []));

// An app that reads questions (its hello says `pictures`), as the editor's preview and ESP Screen Manager are.
const raw = packet => m.ccall('preview_receive', 'string', ['string'], [JSON.stringify(packet)]);
const granted = raw({ v: 2, op: 'hello', request: '1111111111111111', features: ['pictures'] });
assert.match(granted, /^Session:[0-9a-f]{16}$/);
let seq = 0;
const receive = packet => {
  const result = raw({ ...packet, v: 2, session: granted.slice(8), seq: ++seq, rev: '2222222222222222' });
  assert.ok(['Synced', 'Loading tiles'].includes(result), `${packet.op}: ${result}`);
};
// Two pages: the first with a background, the second without. On the first, a whole card and one of 40 percent
// (firmware 0.67.0, option opacity), through which the background shows.
const card = (i, slot, o) => ({ op: 'tile', i, slot, entity: `switch.card_${i}`, name: '', state: 'off', a: {}, o });
receive({ op: 'begin', title: 'Backdrop', pages: 2, tiles: 2, home: 0, keepalive: 60 });
receive({ op: 'page', p: 0, id: '0000000000000001', title: '', home_control: false, excluded: false, items: [], bg: 'a1b2c3d4e5f6' });
receive({ op: 'page', p: 1, id: '0000000000000002', title: '', home_control: false, excluded: false, items: [] });
receive(card(0, 0, {}));
receive(card(1, 1, { opacity: 40 }));
receive({ op: 'commit' });

function bmp(w, h) {
  const offset = 54, stride = Math.ceil(w * 3 / 4) * 4;
  const bytes = Buffer.alloc(offset + stride * h);
  bytes.write('BM'); bytes.writeUInt32LE(bytes.length, 2); bytes.writeUInt32LE(offset, 10);
  bytes.writeUInt32LE(40, 14); bytes.writeUInt32LE(w, 18); bytes.writeUInt32LE(h, 22);
  bytes.writeUInt16LE(1, 26); bytes.writeUInt16LE(24, 28);
  // Bottom-up: the upper half red, the lower half green.
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) bytes[offset + y * stride + x * 3 + (y < h / 2 ? 1 : 2)] = 255;
  return bytes;
}

// The firmware asks for the first page's background, and only that.
let asked = null;
for (let i = 0; i < 10 && !asked; i++) {
  tick();
  for (let text = nextAction(); text; text = nextAction()) {
    const action = JSON.parse(text);
    if (action.service !== 'esphome.screen_camera' || !action.data.q) continue;
    const q = JSON.parse(action.data.q);
    if (q.o === 'page') { asked = { q, n: Number(action.data.n) }; break; }
  }
}
assert.ok(asked, 'the firmware asks for the page\'s background');
assert.equal(asked.q.i, 0);
assert.deepEqual(asked.q.src, ['page:0']);
assert.deepEqual(asked.q.fit, ['cover']);
assert.equal(asked.q.fmt[0], 'bmp16', 'in the glass\'s own colours first');
const [w, h] = asked.q.box;
assert.ok(w > 0 && w <= width && h > 0 && h <= height, `a picture of the glass: ${w}x${h}`);

// An answer with a number no page asked under is dropped; the page's own is taken.
receive({ op: 'camera', t: 'q', n: asked.n + 1000, u: 'http://firmware-preview.invalid/zzzzzzzzzzzzzzzz.bmp' });
receive({ op: 'camera', t: 'q', n: asked.n, u: 'http://firmware-preview.invalid/abcdefghijklmnop.bmp' });
tick(800);
const request = nextImage();
assert.ok(request && request.id, 'the firmware downloads the answer\'s picture');
assert.match(request.url, /abcdefghijklmnop/);
const body = bmp(w, h);
const pointer = m._preview_image_buffer(request.id, body.length);
assert.ok(pointer);
m.HEAPU8.set(body, pointer);
assert.equal(m._preview_image_ready(request.id, 1), 1);
tick(); tick();

// Behind the whole glass: one picture of the glass's size, red above and green below.
const shown = diagnostics().images.filter((image) => image.width === width && image.height === height);
assert.equal(shown.length, 1, JSON.stringify(diagnostics().images));
const frame = m._preview_frame();
const pixel = (x, y) => { const start = frame + (y * width + x) * 4; return [...m.HEAPU8.subarray(start, start + 3)]; };
const left = 2;
assert.deepEqual(pixel(left, Math.floor(height * 0.3)), [255, 0, 0], 'the picture shows through the empty page');
assert.deepEqual(pixel(left, Math.floor(height * 0.7)), [0, 255, 0]);

// The whole card covers the picture with its own colour; the card of 40 percent lets the red through, mixed.
const tiles = diagnostics().tiles;
assert.equal(tiles.length, 2, JSON.stringify(tiles));
const inside = (t) => pixel(t.x + t.width - 16, t.y + 16);
const [whole, through] = [...tiles].sort((a, b) => a.x - b.x || a.y - b.y).map(inside);
assert.ok(!(whole[0] > 200 && whole[1] < 60), `a whole card hides the picture: ${whole}`);
assert.ok(through[0] > 200 && through[1] > 60 && through[1] < 230 && through[2] > 60 && through[2] < 230,
  `a card of 40 percent shows the red through it: ${through}`);

console.log(`PASS ${width}x${height}: a page's background is asked as page:0, answered by its own number, decoded and shown behind the glass`);

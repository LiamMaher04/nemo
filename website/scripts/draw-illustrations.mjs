/**
 * Draws the scenes for "How it works" and "Privacy" into public/illustrations.
 * Run: npm run draw:illustrations
 *
 * The look is a two-colour print: brush lines that swell and taper, flat colour
 * laid slightly off-register, hatching for shade. No gradients or soft shadows.
 * The random numbers are seeded, so the output only changes when this file does.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const NAVY = "#1B3A5B";
const CORAL = "#FF7A59";
const AQUA = "#3B9FA6";
const PAPER = "#FBF7EF";
const SAND = "#E8DCC8";
const OAK = "#D6BE9A";
const MIST = "#CFE2DF";
const PANEL = "#2A4F75";
const NAVY_LO = "#142C46";

let seed = 1;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const between = (a, b) => a + rnd() * (b - a);

let out = [];
let M = [1, 0, 0, 1, 0, 0];
const f = (n) => n.toFixed(1).replace(/\.0$/, "");

function at({ x = 0, y = 0, s = 1, sy = s, rot = 0 }, draw) {
  const saved = M;
  const c = Math.cos((rot * Math.PI) / 180);
  const n = Math.sin((rot * Math.PI) / 180);
  const [a, b, d, e, g, h] = M;
  const l = [c * s, n * s, -n * sy, c * sy, x, y];
  M = [
    a * l[0] + d * l[1],
    b * l[0] + e * l[1],
    a * l[2] + d * l[3],
    b * l[2] + e * l[3],
    a * l[4] + d * l[5] + g,
    b * l[4] + e * l[5] + h,
  ];
  draw();
  M = saved;
}
const T = ([x, y]) => [M[0] * x + M[2] * y + M[4], M[1] * x + M[3] * y + M[5]];

function curve(pts, closed, step = 5) {
  const n = pts.length;
  const res = [];
  const get = (i) => (closed ? pts[(i + n) % n] : pts[Math.max(0, Math.min(n - 1, i))]);
  for (let i = 0; i < (closed ? n : n - 1); i++) {
    const [p0, p1, p2, p3] = [get(i - 1), get(i), get(i + 1), get(i + 2)];
    const k = Math.max(1, Math.round(Math.hypot(p2[0] - p1[0], p2[1] - p1[1]) / step));
    for (let j = 0; j < k; j++) {
      const t = j / k;
      const c = (a, b, c2, d) =>
        0.5 * (2 * b + (c2 - a) * t + (2 * a - 5 * b + 4 * c2 - d) * t * t + (3 * b - a - 3 * c2 + d) * t * t * t);
      res.push([c(p0[0], p1[0], p2[0], p3[0]), c(p0[1], p1[1], p2[1], p3[1])]);
    }
  }
  if (!closed) res.push(pts[n - 1]);
  return res;
}

function drift(n) {
  const [a, b, c] = [rnd() * 6.3, rnd() * 6.3, between(0.11, 0.2)];
  const d = between(0.31, 0.47);
  return (i) => 0.65 * Math.sin(a + i * c) + 0.35 * Math.sin(b + i * d) + 0 * n;
}

function shaky(line, amp) {
  const nx = drift(line.length);
  const ny = drift(line.length);
  return line.map(([x, y], i) => [x + nx(i) * amp, y + ny(i) * amp]);
}

const polygon = (line) => "M" + line.map(([x, y]) => `${f(x)} ${f(y)}`).join("L") + "Z";

/** A brush line that swells and tapers. Closed shapes overshoot where the pen meets its start. */
function ink(pts, { w = 3, c = NAVY, closed = false, amp = 0.55 } = {}) {
  let line = curve(pts.map(T), closed);
  if (closed) {
    const over = Math.max(2, Math.round(line.length * 0.06));
    line = [...line, ...line.slice(0, over).map(([x, y]) => [x + between(-0.6, 0.6), y + between(-0.6, 0.6)])];
  }
  line = shaky(line, amp);
  const n = line.length;
  if (n < 2) return;
  const swell = drift(n);
  const left = [];
  const right = [];
  const edge = Math.max(1, n * 0.14);
  for (let i = 0; i < n; i++) {
    const p = line[Math.max(0, i - 1)];
    const q = line[Math.min(n - 1, i + 1)];
    const len = Math.hypot(q[0] - p[0], q[1] - p[1]) || 1;
    const [ux, uy] = [(q[0] - p[0]) / len, (q[1] - p[1]) / len];
    const end = Math.min(1, 0.22 + i / edge, 0.22 + (n - 1 - i) / edge);
    const h = (w / 2) * end * (0.95 + 0.36 * swell(i));
    left.push([line[i][0] - uy * h, line[i][1] + ux * h]);
    right.unshift([line[i][0] + uy * h, line[i][1] - ux * h]);
  }
  out.push(`<path fill="${c}" d="${polygon([...left, ...right])}"/>`);
}

/** Flat colour, laid slightly off-register from the line work. */
function fill(pts, c, { mis = [1.8, -1.4], amp = 0.9 } = {}) {
  const line = shaky(curve(pts.map(T), true, 7), amp).map(([x, y]) => [x + mis[0], y + mis[1]]);
  out.push(`<path fill="${c}" d="${polygon(line)}"/>`);
}

function line(a, b, opts) {
  const mid = [(a[0] + b[0]) / 2 + between(-0.7, 0.7), (a[1] + b[1]) / 2 + between(-0.7, 0.7)];
  ink([a, mid, b], opts);
}

function hatch(a, b, count, dx, dy, w = 1.4, c = NAVY) {
  for (let i = 0; i < count; i++) {
    const t = (i + between(-0.25, 0.25)) / Math.max(1, count - 1);
    const s = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    const k = between(0.75, 1.15);
    line(s, [s[0] + dx * k, s[1] + dy * k], { w, c, amp: 0.3 });
  }
}

const inside = (p, poly) => {
  let hit = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [a, b] = [poly[i], poly[j]];
    if (a[1] > p[1] !== b[1] > p[1] && p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]) hit = !hit;
  }
  return hit;
};

/** Little gaps where the ink did not quite take. */
function flecks(pts, count, c = PAPER) {
  const poly = pts.map(T);
  const xs = poly.map((p) => p[0]);
  const ys = poly.map((p) => p[1]);
  let dots = "";
  for (let i = 0; i < count; i++) {
    const p = [between(Math.min(...xs), Math.max(...xs)), between(Math.min(...ys), Math.max(...ys))];
    if (inside(p, poly)) dots += `<circle cx="${f(p[0])}" cy="${f(p[1])}" r="${between(0.35, 1.15).toFixed(2)}"/>`;
  }
  out.push(`<g fill="${c}">${dots}</g>`);
}

/** A hand-ruled rectangle: straight sides, tight corners. */
function box(x, y, w, h, r = 2) {
  const side = (a, b) => {
    const steps = Math.max(3, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / Math.max(8, Math.min(w, h) / 3)));
    return Array.from({ length: steps }, (_, i) => [a[0] + ((b[0] - a[0]) * i) / steps, a[1] + ((b[1] - a[1]) * i) / steps]);
  };
  const c = r * 0.3;
  return [
    [x + c, y + c],
    ...side([x + r, y], [x + w - r, y]),
    [x + w - r, y],
    [x + w - c, y + c],
    ...side([x + w, y + r], [x + w, y + h - r]),
    [x + w, y + h - r],
    [x + w - c, y + h - c],
    ...side([x + w - r, y + h], [x + r, y + h]),
    [x + r, y + h],
    [x + c, y + h - c],
    ...side([x, y + h - r], [x, y + r]),
    [x, y + r],
  ];
}

function oval(cx, cy, rx, ry, n = 12) {
  return Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2;
    return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry];
  });
}

function shadowed(pts, c, offset = [7, 8]) {
  fill(pts.map(([x, y]) => [x + offset[0], y + offset[1]]), NAVY_LO, { mis: [0, 0] });
  fill(pts, c, { mis: [0, 0] });
}

function device({ cable = 0 } = {}) {
  if (cable) {
    fill(box(21.2, -cable, 5.4, cable, 0), PAPER);
    ink([[21.2, -cable], [21.3, 0]], { w: 2.2 });
    ink([[26.6, -cable], [26.5, 0]], { w: 2.2 });
    fill(box(19, -7, 9.8, 7, 1), PAPER);
    ink(box(19, -7, 9.8, 7, 1), { w: 2.2, closed: true });
  }
  fill(box(60.6, 25.4, 5.2, 8.8, 1), PAPER);
  ink(box(60.6, 25.4, 5.2, 8.8, 1), { w: 2.4, closed: true });
  const body = box(0, 0, 61, 113, 4);
  fill(body, PAPER);
  ink(body, { w: 3.4, closed: true });
  // Shade down the right edge, and the sparkle in the filament
  hatch([58.5, 52], [58.5, 111], 15, -3.4, 2.4, 1);
  for (let i = 0; i < 16; i++) {
    const p = [between(5, 56), between(5, 80)];
    if (Math.hypot(p[0] - 30.5, p[1] - 45) > 13) ink(oval(p[0], p[1], 0.35, 0.35, 5), { w: 0.9, closed: true, amp: 0 });
  }
  // Microphones
  fill(oval(47, 24.4, 1.2, 1.3, 7), NAVY, { mis: [0, 0], amp: 0.1 });
  fill(oval(44.4, 28.4, 1.2, 1.3, 7), NAVY, { mis: [0, 0], amp: 0.1 });
  // Camera
  ink(oval(30.5, 45.2, 9.3, 9.3, 12), { w: 2, closed: true });
  fill(oval(30.5, 45.2, 7.4, 7.4, 12), NAVY, { mis: [0.4, -0.3], amp: 0.2 });
  at({ x: 30.5, y: 45.2 }, () => ink(oval(0, 0, 3.6, 3.6, 10), { w: 0.9, c: PAPER, closed: true, amp: 0.1 }));
  fill(oval(27.8, 42.3, 1.6, 1.1, 7), PAPER, { mis: [0, 0], amp: 0.1 });
  // Screen
  ink(box(17.5, 88, 26, 16, 1), { w: 2, closed: true });
  fill(box(19.8, 90.2, 21.4, 11.6, 0.6), NAVY, { mis: [0.3, -0.2], amp: 0.2 });
  const eye = (cx) => [[cx - 3, 97.2], [cx - 2.7, 95], [cx, 93.9], [cx + 2.7, 95], [cx + 3, 97.2]];
  fill(eye(26.4), AQUA, { mis: [0, 0], amp: 0.05 });
  fill(eye(34.8), AQUA, { mis: [0, 0], amp: 0.05 });
  ink([[33.6, 99.3], [37, 99.3]], { w: 1, c: AQUA, amp: 0 });
}

function keyShape() {
  const arc = Array.from({ length: 10 }, (_, i) => {
    const a = (25 + (i / 9) * 310) * (Math.PI / 180);
    return [9 + Math.cos(a) * 14, Math.sin(a) * 14];
  });
  const pts = [
    ...arc,
    [22, -5], [50, -5], [72, -5], [79, 0], [79, 5], [73, 5], [70, 9.5], [66, 5], [62, 9.5], [58, 5], [54, 8.5], [50, 5], [24, 5],
  ];
  fill(pts, PAPER, { mis: [1, -0.7], amp: 0.2 });
  ink(pts, { w: 2.1, closed: true, amp: 0.25 });
  ink(oval(1, 0, 4.2, 4.2, 8), { w: 1.3, closed: true, amp: 0.1 });
  ink([[27, 0], [69, 0]], { w: 1, amp: 0.2 });
}

/** A bunch of keys lying on a surface, ring in the middle. */
function keys() {
  hatch([-54, 22], [78, 26], 30, -7, 7, 1);
  at({ sy: 0.62 }, () => {
    at({ rot: 160, x: 0, y: 0 }, () => {
      const fob = box(14, -15, 58, 30, 8);
      fill(fob, CORAL);
      ink(fob, { w: 2.4, closed: true, amp: 0.3 });
      for (let i = 0; i < 12; i++) line([20 + i * 4.3, -10.5], [22.4 + i * 4.3, -10.5], { w: 1, c: PAPER, amp: 0 });
      for (let i = 0; i < 12; i++) line([20 + i * 4.3, 10.5], [22.4 + i * 4.3, 10.5], { w: 1, c: PAPER, amp: 0 });
      ink(oval(21, 0, 3.6, 3.6, 8), { w: 1.3, closed: true, amp: 0.1 });
    });
    at({ rot: 8 }, () => at({ x: 8 }, keyShape));
    at({ rot: -28 }, () => at({ x: 8 }, keyShape));
    ink(oval(0, 0, 16, 16, 14), { w: 2.4, closed: true, amp: 0.2 });
  });
}

/** Round reading glasses, bridge in the middle, resting on y=0. */
function glasses() {
  hatch([-62, 5], [62, 5], 34, -8, 5, 1.1);
  for (const m of [1, -1]) {
    ink([[m * 58, -39], [m * 71, -33], [m * 79, -8]], { w: 2.6, amp: 0.3 });
    const lens = oval(m * 32, -26, 25.5, 24, 14);
    fill(lens, PAPER, { mis: [1.2, -1], amp: 0.3 });
    ink(lens, { w: 4, closed: true, amp: 0.35 });
    ink(oval(m * 32, -26, 21, 19.6, 14).slice(7, 12), { w: 1.1, amp: 0.2 });
    line([m * 32 - 12, -24], [m * 32 - 2, -38], { w: 1.2, amp: 0.1 });
    line([m * 32 - 6, -19], [m * 32 + 4, -33], { w: 1.2, amp: 0.1 });
  }
  ink([[-8, -36], [0, -42], [8, -36]], { w: 3.6, amp: 0.2 });
}

function remote() {
  const r = box(-14, -50, 28, 100, 7);
  fill(r, NAVY, { mis: [1.4, -1] });
  ink(r, { w: 2.2, closed: true, c: NAVY });
  fill(oval(0, -36, 4.6, 4.6, 8), CORAL, { mis: [0, 0], amp: 0.2 });
  for (let row = 0; row < 3; row++)
    for (let col = 0; col < 3; col++) fill(box(-9 + col * 7, -22 + row * 10, 4, 5.4, 1), PAPER, { mis: [0, 0], amp: 0.2 });
  line([-7, 18], [7, 18], { w: 3, c: PAPER, amp: 0.1 });
  line([-7, 29], [7, 29], { w: 3, c: PAPER, amp: 0.1 });
}

/** A finger coming in from the right, tip at the origin, with the rest of the hand curled behind. */
function hand() {
  const shape = [
    [-9, 1], [-7, -11], [3, -17], [36, -22], [84, -30], [132, -46], [230, -60], [240, 160], [150, 160],
    [138, 122], [122, 100], [128, 72], [110, 52], [114, 34], [90, 24], [46, 20], [4, 17], [-6, 11],
  ];
  fill(shape, SAND);
  ink([[-9, 1], [-7, -11], [3, -17], [36, -22], [84, -30], [132, -46], [230, -60]], { w: 3.4 });
  ink([[230, 26], [152, 24], [90, 24], [46, 20], [4, 17], [-6, 11], [-9, 1]], { w: 3.4 });
  // The other fingers, curled under
  ink([[150, 28], [118, 28], [104, 40], [112, 54], [150, 56]], { w: 3 });
  ink([[152, 58], [120, 58], [108, 72], [118, 86], [160, 88]], { w: 3 });
  ink([[160, 90], [132, 92], [122, 106], [136, 124], [150, 160]], { w: 3 });
  // Nail and knuckle
  ink([[-3, -11], [18, -13], [28, -11], [29, 3], [24, 11], [4, 12]], { w: 1.8 });
  ink([[70, -24], [66, -10], [70, 14]], { w: 1.5 });
  ink([[79, -26], [75, -8], [79, 15]], { w: 1.3 });
  hatch([46, 15], [108, 19], 12, 3, -8, 1);
}

function scene(name, w, h, background, draw) {
  seed = [...name].reduce((a, ch) => a * 31 + ch.charCodeAt(0), 7) % 2147483646 || 1;
  out = [];
  M = [1, 0, 0, 1, 0, 0];
  const block = box(10, 10, w - 20, h - 20, 1);
  const edge = shaky(curve(block, true, 9), 1.5);
  out.push(`<path fill="${background}" d="${polygon(edge)}"/>`);
  flecks(block, Math.round((w * h) / 620), background === PANEL ? "#34597F" : PAPER);
  out.push(`<g clip-path="url(#b)">`);
  draw();
  out.push("</g>");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}"><defs><clipPath id="b"><path d="${polygon(edge)}"/></clipPath></defs>${out.join("")}</svg>\n`;
  const dest = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "illustrations", `${name}.svg`);
  mkdirSync(dirname(dest), { recursive: true });
  writeFileSync(dest, svg);
  console.log(`${name}.svg  ${(svg.length / 1024).toFixed(0)} KB`);
}

scene("notice", 480, 360, SAND, () => {
  // Light falling across the wall
  hatch([300, 20], [470, 20], 22, -46, 110, 1, "#CDBD9F");
  // The table, with Nemo's wearer standing beside it
  const table = [[210, 262], [480, 256], [480, 300], [210, 306]];
  fill(table, OAK, { mis: [0, 0] });
  fill([[210, 306], [480, 300], [480, 370], [210, 370]], NAVY, { mis: [0, 0] });
  ink([[230, 262], [360, 258], [480, 256]], { w: 3 });
  ink([[230, 305], [360, 301], [480, 300]], { w: 3 });
  for (const y of [270, 280, 291]) ink([[250 + y / 4, y], [340 + y / 6, y - 1.4], [470, y - 3]], { w: 0.9 });
  at({ x: 352, y: 279 }, () => at({ s: 0.95, rot: -4 }, keys));
  const jumper = [[-20, -20], [170, -20], [214, 66], [240, 160], [250, 262], [258, 380], [-20, 380]];
  fill(jumper, AQUA, { mis: [0, 0] });
  flecks(jumper, 170);
  ink([[172, -6], [214, 66], [240, 160], [250, 262], [258, 372]], { w: 3.4 });
  ink([[188, 118], [176, 200], [172, 280], [176, 372]], { w: 2.2 });
  ink([[-8, 54], [60, 74], [128, 44], [150, 2]], { w: 3 });
  ink([[-8, 66], [62, 88], [138, 54], [162, 2]], { w: 2 });
  for (let i = 0; i < 18; i++) {
    const x = 2 + i * 8.6;
    const y = 58 + Math.sin(i / 6) * 18 + (i > 9 ? -(i - 9) * 3 : 0);
    line([x, y + 3], [x + 2, y + 15], { w: 1.2, amp: 0.1 });
  }
  for (let row = 0; row < 12; row++)
    for (let col = 0; col < 11; col++) {
      const x = 8 + col * 20 + (row % 2) * 10 + between(-2, 2);
      const y = 100 + row * 24 + between(-2, 2);
      const covered = x > 62 && x < 182 && y > 84 && y < 318;
      if (covered || x > 168 + (y - 100) * 0.1 || rnd() < 0.3) continue;
      ink([[x - 3.4, y - 3], [x, y + 2], [x + 3.4, y - 3]], { w: 1.2, amp: 0.1 });
    }
  at({ x: 66, y: 98 }, () => at({ s: 1.75, rot: -2.5 }, () => device({ cable: 56 })));
});

scene("ask", 480, 360, AQUA, () => {
  flecks(box(10, 10, 460, 340, 1), 130);
  hatch([24, 300], [120, 338], 16, 30, -42, 1.1, "#2F858C");
  at({ x: 96, y: 40 }, () => at({ s: 2.42, rot: 3.5 }, () => device({ cable: 26 })));
  at({ x: 263, y: 121 }, () => at({ s: 0.86, rot: 3 }, hand));
  // The press
  for (const [x, y, dx, dy] of [[250, 76, 6, -16], [270, 80, 15, -14], [288, 92, 19, -8]])
    ink([[x, y], [x + dx / 2 + 1, y + dy / 2], [x + dx, y + dy]], { w: 3.2, c: CORAL, amp: 0.25 });
});

scene("tell", 480, 360, MIST, () => {
  fill(box(10, 10, 460, 214, 1), "#B9D5D1", { mis: [0, 0] });
  const books = [
    [282, 30, 128, CORAL], [312, 23, 112, PAPER], [335, 36, 138, AQUA],
    [371, 25, 118, SAND], [396, 33, 132, NAVY],
  ];
  for (const [x, w, h, c] of books) {
    const b = box(x, 214 - h, w, h, 1.5);
    fill(b, c);
    flecks(b, 14);
    ink(b, { w: 2.8, closed: true, amp: 0.4 });
    const on = c === NAVY ? PAPER : NAVY;
    line([x + 5, 214 - h + 18], [x + w - 5, 214 - h + 18], { w: 2.2, c: on });
    line([x + 5, 214 - h + 25], [x + w - 5, 214 - h + 25], { w: 1, c: on });
    line([x + 7, 196], [x + w - 7, 196], { w: 1.6, c: on });
  }
  at({ x: 430, y: 214 }, () =>
    at({ rot: 13 }, () => {
      const b = box(0, -126, 30, 126, 1.5);
      fill(b, PAPER);
      ink(b, { w: 2.8, closed: true, amp: 0.4 });
      line([5, -108], [25, -108], { w: 2.2 });
    }),
  );
  at({ x: 150, y: 212 }, () => at({ s: 1.2 }, glasses));
  const shelf = [[-10, 214], [490, 214], [490, 234], [-10, 234]];
  fill(shelf, OAK, { mis: [0, 0] });
  ink([[12, 214], [240, 212], [470, 214]], { w: 3.4 });
  ink([[12, 234], [240, 235], [470, 233]], { w: 3 });
  hatch([20, 238], [470, 238], 70, -6, 13, 1.1);
  at({ x: 48, y: 249 }, () => at({ s: 0.8, rot: -3 }, device));
  // Nemo's answer, as a pencilled arrow to the shelf
  ink([[112, 296], [210, 318], [282, 276], [254, 214], [212, 186]], { w: 3.6, c: CORAL, amp: 0.8 });
  ink([[234, 182], [212, 186], [220, 208]], { w: 3.6, c: CORAL, amp: 0.3 });
});

function print(w, h, r, x, y, picture) {
  at({ x, y }, () =>
    at({ rot: r }, () => {
      shadowed(box(-w / 2, -h / 2, w, h, 1), PAPER);
      const iw = w - 18;
      const ih = h - 40;
      at({ x: -iw / 2, y: -h / 2 + 9 }, () => picture(iw, ih));
      ink(box(-iw / 2, -h / 2 + 9, iw, ih, 0.5), { w: 1.8, closed: true, amp: 0.4 });
    }),
  );
}

scene("snapshots", 480, 300, PANEL, () => {
  print(150, 172, -11, 112, 160, (w, h) => {
    fill(box(0, 0, w, h, 0), MIST, { mis: [0, 0] });
    fill(box(0, h * 0.66, w, h * 0.34, 0), OAK, { mis: [0, 0] });
    at({ x: w / 2, y: h * 0.76 }, () => at({ s: 0.62 }, glasses));
  });
  print(150, 172, 10, 366, 160, (w, h) => {
    fill(box(0, 0, w, h, 0), SAND, { mis: [0, 0] });
    fill(box(0, h * 0.52, w, h * 0.48, 0), AQUA, { mis: [0, 0] });
    at({ x: w / 2, y: h * 0.56 }, () => at({ s: 0.66, rot: 62 }, remote));
  });
  print(158, 182, 1.5, 240, 150, (w, h) => {
    fill(box(0, 0, w, h, 0), SAND, { mis: [0, 0] });
    fill(box(0, h * 0.58, w, h * 0.42, 0), OAK, { mis: [0, 0] });
    at({ x: w / 2 - 2, y: h * 0.76 }, () => at({ s: 0.72 }, keys));
  });
});

scene("face", 480, 300, PANEL, () => {
  print(330, 256, -2, 240, 150, (w, h) => {
    fill(box(0, 0, w, h, 0), SAND, { mis: [0, 0] });
    const win = box(26, 18, 74, 92, 0.5);
    fill(win, MIST);
    ink(win, { w: 2.4, closed: true });
    ink([[63, 18], [63, 110]], { w: 1.8 });
    ink([[26, 62], [100, 62]], { w: 1.8 });
    const body = [[84, 220], [92, 148], [132, 122], [188, 122], [226, 148], [234, 220]];
    fill(body, AQUA);
    ink(body, { w: 2.8 });
    ink([[136, 121], [159, 136], [183, 121]], { w: 2.2 });
    ink([[145, 98], [146, 126]], { w: 2 });
    ink([[174, 98], [173, 126]], { w: 2 });
    // The face, broken into dots the way a blurred photo breaks up
    let dots = "";
    const [cx, cy] = [159, 72];
    for (let gy = -66; gy <= 70; gy += 6.2)
      for (let gx = -56; gx <= 56; gx += 6.2) {
        const px = gx + (Math.round(gy / 6.2) % 2 ? 3.1 : 0);
        const fall = 1 - Math.hypot(px / 53, gy / 68);
        if (fall <= 0.02) continue;
        const [sx, sy] = T([cx + px, cy + gy]);
        dots += `<circle cx="${f(sx)}" cy="${f(sy)}" r="${Math.min(3, 0.7 + fall * 3.8).toFixed(2)}"/>`;
      }
    out.push(`<g fill="#B79C7C">${dots}</g>`);
    fill(box(0, h * 0.8, w, h * 0.2, 0), OAK, { mis: [0, 0] });
    ink([[2, h * 0.8], [w / 2, h * 0.8 - 1.5], [w - 2, h * 0.8]], { w: 2.4 });
    at({ x: 248, y: h * 0.88 }, () => at({ s: 0.48 }, glasses));
    at({ x: 66, y: h * 0.89 }, () => at({ s: 0.48 }, keys));
  });
});

scene("listen", 480, 300, PANEL, () => {
  flecks(box(10, 10, 460, 280, 1), 40, "#34597F");
  const pos = { x: 76, y: 46 };
  fill(box(pos.x + 8, pos.y + 10, 61 * 3.65, 400, 8), NAVY_LO, { mis: [0, 0] });
  at(pos, () => at({ s: 3.65 }, () => device({ cable: 18 })));
  at({ x: 328, y: 156 }, () => at({ s: 1.12 }, hand));
  for (const [x, y, dx, dy] of [[318, 104, 6, -19], [342, 108, 17, -17], [362, 122, 22, -10]])
    ink([[x, y], [x + dx / 2 + 1, y + dy / 2], [x + dx, y + dy]], { w: 3.4, c: CORAL, amp: 0.25 });
});

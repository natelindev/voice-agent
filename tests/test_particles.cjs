// Run with: node --test tests/test_particles.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/voice_agent/web/static/particles.js', 'utf8');

function setup({ reducedMotion = false } = {}) {
  const frames = new Map();
  const listeners = {};
  let nextFrame = 0;
  let bounds = { width: 400, height: 400 };
  const points = [];
  const ctx = {
    setTransform(...args) { this.transform = args; },
    clearRect() { points.length = 0; },
    beginPath() {}, fill() {},
    arc(x, y, radius) { points.push({ x, y, radius }); },
  };
  const canvas = { getContext: () => ctx, getBoundingClientRect: () => bounds };
  const motion = {
    matches: reducedMotion,
    addEventListener: (_, callback) => { listeners.motion = callback; },
    removeEventListener: () => { delete listeners.motion; },
  };
  const document = {
    hidden: false,
    getElementById: () => canvas,
    addEventListener: (_, callback) => { listeners.visibility = callback; },
    removeEventListener: () => { delete listeners.visibility; },
  };
  const window = {
    devicePixelRatio: 3,
    matchMedia: () => motion,
    addEventListener: (_, callback) => { listeners.resize = callback; },
    removeEventListener: () => { delete listeners.resize; },
  };
  vm.runInNewContext(source, {
    window, document,
    requestAnimationFrame: callback => { frames.set(++nextFrame, callback); return nextFrame; },
    cancelAnimationFrame: id => frames.delete(id),
    ResizeObserver: class { observe() {} disconnect() {} },
  });
  const field = new window.VoiceParticles('canvas');
  function tick(timestamp) {
    const [id, callback] = frames.entries().next().value;
    frames.delete(id);
    callback(timestamp);
  }
  return { field, frames, points, ctx, canvas, motion, document, listeners, tick,
    setBounds(value) { bounds = value; } };
}

test('voice energy expands a field of individual dots without a filled core', () => {
  const quiet = setup();
  const speech = setup();
  quiet.field.setState('speaking');
  speech.field.setState('speaking');
  speech.field.setAudioLevel(0.9);
  for (let i = 0; i < 180; i++) {
    quiet.tick(i * 1000 / 60);
    speech.tick(i * 1000 / 60);
  }
  const extent = points => Math.max(...points.map(p => Math.hypot(p.x - 200, p.y - 200)));
  assert.ok(extent(speech.points) > extent(quiet.points) * 1.05);
  assert.equal(speech.points.length, speech.field.particles.length);
  assert.ok(speech.points.every(p => Number.isFinite(p.x) && Number.isFinite(p.y) && p.radius < 2));
  speech.field.setAudioLevel(NaN);
  assert.equal(speech.field.targetLevel, 0);
  speech.field.setAudioLevel(10);
  assert.equal(speech.field.targetLevel, 1);
  speech.field.setState('unknown');
  assert.equal(speech.field.state, 'idle');
});

test('motion follows elapsed time at different refresh rates', () => {
  const sixty = setup();
  const oneTwenty = setup();
  sixty.field.setState('thinking');
  oneTwenty.field.setState('thinking');
  for (let i = 0; i <= 180; i++) sixty.tick(i * 1000 / 60);
  for (let i = 0; i <= 360; i++) oneTwenty.tick(i * 1000 / 120);
  assert.ok(Math.abs(sixty.field.rotation - oneTwenty.field.rotation) < 0.01);
  assert.ok(Math.abs(sixty.points[0].x - oneTwenty.points[0].x) < 1);
});

test('reduced motion renders a static field and never loops on audio events', () => {
  const env = setup({ reducedMotion: true });
  const before = JSON.stringify(env.points);
  assert.equal(env.frames.size, 0);
  env.field.setAudioLevel(1);
  assert.equal(JSON.stringify(env.points), before);
  env.field.setState('thinking');
  assert.equal(env.frames.size, 0);
  assert.ok(env.points.length > 1000);
  env.motion.matches = false;
  env.listeners.motion();
  assert.equal(env.frames.size, 1);
  env.motion.matches = true;
  env.listeners.motion();
  assert.equal(env.frames.size, 0);
});

test('resize, hidden-tab resume and cleanup keep a single animation loop', () => {
  const env = setup();
  assert.equal(env.canvas.width, 800); // DPR is capped at 2.
  env.setBounds({ width: 260, height: 260 });
  env.listeners.resize();
  assert.equal(env.canvas.width, 520);
  assert.equal(env.frames.size, 1);
  env.tick(0);
  env.document.hidden = true;
  env.listeners.visibility();
  assert.equal(env.frames.size, 0);
  env.document.hidden = false;
  env.listeners.visibility();
  assert.equal(env.frames.size, 1);
  env.tick(100000);
  assert.ok(env.field.time < 0.1); // No huge simulation jump after tab sleep.
  env.field.destroy();
  assert.equal(env.frames.size, 0);
  assert.equal(Object.keys(env.listeners).length, 0);
});

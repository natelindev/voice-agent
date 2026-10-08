// Client behavior tests use DOM/event doubles; no browser or npm dependencies.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/voice_agent/web/static/app.js', 'utf8');
const localeSource = fs.readFileSync('src/voice_agent/web/static/i18n.js', 'utf8');

function setup({ language = 'en', savedLanguage = null } = {}) {
  const elements = new Map();
  class Element {
    constructor(id = '') {
      this.id = id;
      this.style = {};
      this.dataset = {};
      this.attributes = {};
      this.children = [];
      this.listeners = {};
      this.disabled = false;
      this.textContent = '';
      this.classList = { add() {}, remove() {} };
    }
    setAttribute(key, value) { this.attributes[key] = String(value); }
    getAttribute(key) { return this.attributes[key] ?? null; }
    removeAttribute(key) { delete this.attributes[key]; }
    addEventListener(type, callback) { this.listeners[type] = callback; }
    appendChild(element) { this.children.push(element); }
    replaceChildren(...children) { this.children = children; }
    set innerHTML(html) {
      this.html = html;
      // Model replacing the empty-state node, the original clear-history bug.
      if (html.includes('id="emptyState"')) {
        const empty = new Element('emptyState');
        elements.set('emptyState', empty);
        this.children = [empty];
      }
    }
    get innerHTML() { return this.html || this.textContent; }
  }
  const getElement = id => {
    if (!elements.has(id)) elements.set(id, new Element(id));
    return elements.get(id);
  };
  const steps = ['listen', 'understand', 'think', 'speak'].map(step => {
    const element = new Element();
    element.dataset.step = step;
    return element;
  });
  const app = new Element('app');
  const events = {};
  const commands = [];
  const visualizer = { setState(state) { this.state = state; }, setAudioLevel() {} };
  let socket;
  class Socket {
    static OPEN = 1;
    constructor() { socket = this; this.readyState = 0; }
    send(packet) { commands.push(JSON.parse(packet)); }
    close() { this.readyState = 3; this.onclose(); }
    open() { this.readyState = 1; this.onopen(); }
    receive(event) { this.onmessage({ data: JSON.stringify(event) }); }
  }
  const storage = new Map(savedLanguage ? [['voice-agent-language', savedLanguage]] : []);
  const context = vm.createContext({
    document: {
      documentElement: new Element('html'),
      getElementById: getElement,
      querySelector: () => app,
      querySelectorAll: selector => selector === '[data-step]' ? steps : [],
      createElement: () => new Element(),
    },
    window: {
      location: { protocol: 'http:', host: 'localhost' },
      addEventListener: (type, callback) => { events[type] = callback; },
      dispatchEvent: event => events[event.type]?.(event),
    },
    VoiceParticles: class { constructor() { return visualizer; } },
    AudioWaveform: class { setAudioLevel() {} },
    WebSocket: Socket,
    navigator: { language },
    localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    setTimeout() {}, console,
  });
  vm.runInContext(localeSource, context);
  vm.runInContext(source, context);
  const feed = getElement('chatFeed');
  feed.children = [getElement('emptyState')];
  const key = (value, interactive = false) => {
    let prevented = false;
    events.keydown({ key: value, code: value === ' ' ? 'Space' : '',
      target: { closest: () => interactive ? {} : null },
      preventDefault: () => { prevented = true; } });
    return prevented;
  };
  socket.open();
  socket.receive({ event_type: 'state_change', state: 'listening', backend: 'demo', is_muted: false });
  return { getElement, socket, commands, steps, app, key, visualizer,
    i18n: context.window.VoiceI18n, document: context.document, storage };
}

test('clear history hides its restored empty state when the next transcript arrives', () => {
  const env = setup();
  const feed = env.getElement('chatFeed');
  env.socket.receive({ event_type: 'transcript', role: 'user', text: 'First turn' });
  assert.equal(env.getElement('emptyState').style.display, 'none');
  env.getElement('clearBtn').listeners.click();
  assert.equal(feed.children.length, 1);
  assert.equal(feed.children[0].style.display, '');
  assert.equal(env.getElement('turnCount').textContent, '0 turns');
  env.socket.receive({ event_type: 'transcript', role: 'user', text: 'Next turn' });
  assert.equal(feed.children[0].style.display, 'none');
  assert.equal(feed.children.length, 2);
  assert.equal(env.getElement('turnCount').textContent, '1 turn');
});

test('mute and connection loss update visible state and accessible controls', () => {
  const env = setup();
  const mute = env.getElement('muteBtn');
  mute.listeners.click();
  assert.equal(mute.attributes['aria-pressed'], 'true');
  assert.equal(mute.attributes['aria-label'], 'Unmute microphone');
  assert.equal(env.getElement('statusText').textContent, 'Muted');
  assert.equal(env.getElement('stateHeadline').textContent, 'Microphone off.');
  mute.listeners.click();
  assert.equal(mute.attributes['aria-pressed'], 'false');
  assert.equal(env.getElement('stateHeadline').textContent, 'Listening.');
  env.socket.receive({ event_type: 'state_change', state: 'thinking' });
  assert.equal(env.steps[2].attributes['aria-current'], 'step');
  env.socket.close();
  assert.equal(mute.disabled, true);
  assert.equal(env.getElement('interruptBtn').disabled, true);
  assert.equal(env.getElement('statusText').textContent, 'Reconnecting');
  assert.equal(env.getElement('inputMeter').attributes['aria-valuenow'], '0');
  assert.equal(env.visualizer.state, 'idle');
  assert.ok(env.steps.every(step => !step.attributes['aria-current']));
});

test('Space on a focused button retains native activation instead of interrupting', () => {
  const env = setup();
  assert.equal(env.key(' ', true), false);
  assert.equal(env.commands.length, 0);
  assert.equal(env.key(' '), true);
  assert.equal(env.commands[0].action, 'interrupt');
  env.key('m');
  assert.equal(env.commands[1].action, 'mute');
});

test('Chinese browser locale covers live states, accessibility, and persisted switching', () => {
  const env = setup({ language: 'zh-CN' });
  assert.equal(env.document.documentElement.lang, 'zh-CN');
  assert.equal(env.getElement('stateHeadline').textContent, '我在听。');
  env.getElement('muteBtn').listeners.click();
  assert.equal(env.getElement('stateHeadline').textContent, '麦克风已关闭。');
  assert.equal(env.getElement('muteBtn').attributes['aria-label'], '开启麦克风');
  env.i18n.setLanguage('en');
  assert.equal(env.getElement('stateHeadline').textContent, 'Microphone off.');
  assert.equal(env.getElement('muteBtn').attributes['aria-pressed'], 'true');
  assert.equal(env.storage.get('voice-agent-language'), 'en');
  assert.equal(setup({ language: 'zh-CN', savedLanguage: 'en' }).i18n.language, 'en');
  env.socket.close();
  env.i18n.setLanguage('zh');
  assert.equal(env.getElement('statusText').textContent, '重新连接中');
  assert.equal(env.getElement('muteBtn').disabled, true);
});

test('Chinese and English catalogs have full key parity and format turn counts', () => {
  const { i18n } = setup();
  assert.deepEqual(Object.keys(i18n.messages.en).sort(), Object.keys(i18n.messages.zh).sort());
  i18n.setLanguage('zh');
  assert.equal(i18n.t('turn.many', { count: 3 }), '3 轮对话');
  assert.equal(i18n.t('latency.value', { seconds: '1.15' }), '1.15 秒');
});

/** A spring-driven 3D particle field, responsive to voice activity. */
class VoiceParticles {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas?.getContext('2d');
    if (!this.ctx) return;

    this.states = {
      idle:            { color: [111, 147, 207], speed: 0.08, spread: 0.96, energy: 0.025 },
      listening:       { color: [85, 185, 238],  speed: 0.13, spread: 1,    energy: 0.05 },
      speech_detected: { color: [94, 216, 207],  speed: 0.21, spread: 1.05, energy: 0.10 },
      transcribing:    { color: [137, 158, 244], speed: 0.26, spread: 0.94, energy: 0.07 },
      thinking:        { color: [169, 145, 244], speed: 0.34, spread: 0.92, energy: 0.11 },
      speaking:        { color: [90, 203, 242],  speed: 0.22, spread: 1.04, energy: 0.09 },
      interrupted:     { color: [226, 133, 167], speed: 0.10, spread: 1.10, energy: 0.04 },
    };
    this.state = 'idle';
    this.config = { ...this.states.idle, color: [...this.states.idle.color] };
    this.audioLevel = 0;
    this.targetLevel = 0;
    this.time = 0;
    this.rotation = 0;
    this.frame = null;
    this.lastTime = null;
    this.destroyed = false;
    this.motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');

    // A seeded distribution keeps the field stable across resize and state changes.
    let seed = 42;
    const random = () => {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      return seed / 4294967296;
    };
    const count = 1400;
    const goldenAngle = Math.PI * (3 - Math.sqrt(5));
    this.particles = Array.from({ length: count }, (_, i) => {
      const y = 1 - 2 * (i + 0.5) / count;
      const ring = Math.sqrt(1 - y * y);
      const angle = i * goldenAngle;
      const radius = i % 11 === 0 ? 1.15 + random() * 0.25 : 0.72 + random() * 0.28;
      const x = Math.cos(angle) * ring;
      const z = Math.sin(angle) * ring;
      return {
        baseX: x, baseY: y, baseZ: z, radius,
        x: x * radius, y: y * radius, z: z * radius,
        vx: 0, vy: 0, vz: 0,
        phase: random() * Math.PI * 2,
        size: 0.55 + random() * 0.8,
        brightness: 0.5 + random() * 0.5,
      };
    });

    this.animate = this.animate.bind(this);
    this.onVisibilityChange = () => this.refresh();
    this.onMotionChange = () => this.refresh();
    this.onResize = () => { this.resize(); this.refresh(); };
    this.motionPreference.addEventListener('change', this.onMotionChange);
    document.addEventListener('visibilitychange', this.onVisibilityChange);
    window.addEventListener('resize', this.onResize);
    this.resizeObserver = new ResizeObserver(this.onResize);
    this.resizeObserver.observe(this.canvas);
    this.onResize();
  }

  resize() {
    const bounds = this.canvas.getBoundingClientRect();
    this.width = bounds.width;
    this.height = bounds.height;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(this.width * dpr);
    this.canvas.height = Math.round(this.height * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  setState(state) {
    if (!this.ctx || this.destroyed) return;
    this.state = Object.hasOwn(this.states, state) ? state : 'idle';
    if (this.motionPreference.matches) this.refresh();
  }

  setAudioLevel(level) {
    this.targetLevel = Number.isFinite(level) ? Math.max(0, Math.min(1, level)) : 0;
  }

  refresh() {
    if (this.destroyed) return;
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
    this.lastTime = null;
    if (document.hidden) return;
    if (this.motionPreference.matches) {
      // Keep a legible static field; audio events never trigger a motion loop.
      this.config = { ...this.states[this.state], color: [...this.states[this.state].color] };
      this.audioLevel = 0;
      this.draw(0, true);
    } else {
      this.frame = requestAnimationFrame(this.animate);
    }
  }

  animate(timestamp) {
    this.frame = null;
    if (this.destroyed || document.hidden || this.motionPreference.matches) return;
    const dt = this.lastTime === null ? 1 / 60 : Math.min((timestamp - this.lastTime) / 1000, 1 / 30);
    this.lastTime = timestamp;
    this.time += dt;
    const target = this.states[this.state];
    const blend = 1 - Math.exp(-dt * 4);
    for (const key of ['speed', 'spread', 'energy']) {
      this.config[key] += (target[key] - this.config[key]) * blend;
    }
    this.config.color = this.config.color.map((value, i) => value + (target.color[i] - value) * blend);
    this.audioLevel += (this.targetLevel - this.audioLevel) * (1 - Math.exp(-dt * 9));
    this.rotation += dt * this.config.speed;
    this.draw(dt, false);
    this.frame = requestAnimationFrame(this.animate);
  }

  draw(dt, staticFrame) {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);
    const scale = Math.min(this.width, this.height) * 0.29;
    const cfg = this.config;
    const audio = this.audioLevel;
    const cos = Math.cos(this.rotation);
    const sin = Math.sin(this.rotation);
    const spring = 38;
    const damping = Math.exp(-9 * dt);
    // Every visible element is an individual particle. No filled body or glow.
    for (const p of this.particles) {
      const wave = Math.sin(p.baseY * 6 + p.phase + this.time * 1.3);
      const radius = p.radius * cfg.spread + wave * (cfg.energy + audio * 0.13) + audio * 0.13;
      const twist = Math.sin(p.baseY * 4 + this.time * 0.7) * (0.10 + audio * 0.12);
      const tx = p.baseX * radius + Math.sin(p.phase + this.time * 0.6) * 0.025;
      const ty = p.baseY * radius;
      const tz = p.baseZ * radius + twist;
      if (staticFrame) {
        p.x = tx; p.y = ty; p.z = tz;
        p.vx = 0; p.vy = 0; p.vz = 0;
      } else {
        p.vx = (p.vx + (tx - p.x) * spring * dt) * damping;
        p.vy = (p.vy + (ty - p.y) * spring * dt) * damping;
        p.vz = (p.vz + (tz - p.z) * spring * dt) * damping;
        p.x += p.vx * dt; p.y += p.vy * dt; p.z += p.vz * dt;
      }
      const x = p.x * cos - p.z * sin;
      const z = p.x * sin + p.z * cos;
      const y = p.y * 0.94 - z * 0.22;
      const depth = Math.max(0, Math.min(1, (z + 1.5) / 3));
      const perspective = 3.8 / (3.8 - z * 0.4);
      const alpha = (0.18 + depth * 0.66) * p.brightness;
      const color = cfg.color.map((value, i) => Math.round(value + (i === 0 ? 36 : 12) * (1 - depth)));
      ctx.fillStyle = `rgba(${color.join(',')},${alpha})`;
      ctx.beginPath();
      ctx.arc(this.width / 2 + x * scale * perspective,
        this.height / 2 + y * scale * perspective,
        p.size * (0.65 + depth * 0.6) * perspective, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  destroy() {
    if (!this.ctx || this.destroyed) return;
    this.destroyed = true;
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.resizeObserver.disconnect();
    this.motionPreference.removeEventListener('change', this.onMotionChange);
    document.removeEventListener('visibilitychange', this.onVisibilityChange);
    window.removeEventListener('resize', this.onResize);
  }
}

window.VoiceParticles = VoiceParticles;

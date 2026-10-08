/** A crisp, quiet signal trace with frame-rate-independent audio response. */
class AudioWaveform {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas?.getContext('2d');
    if (!this.ctx) return;
    this.audioLevel = 0;
    this.targetLevel = 0;
    this.phase = 0;
    this.frame = null;
    this.lastTime = null;
    this.destroyed = false;
    this.motion = matchMedia('(prefers-reduced-motion: reduce)');
    this.animate = this.animate.bind(this);
    this.onVisibility = () => this.refresh();
    this.onMotion = () => this.refresh();
    this.onResize = () => {
      const { width, height } = this.canvas.getBoundingClientRect();
      const dpr = Math.min(devicePixelRatio || 1, 2);
      this.width = width;
      this.height = height;
      this.canvas.width = Math.round(width * dpr);
      this.canvas.height = Math.round(height * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.refresh();
    };
    this.observer = new ResizeObserver(this.onResize);
    this.observer.observe(this.canvas);
    document.addEventListener('visibilitychange', this.onVisibility);
    this.motion.addEventListener('change', this.onMotion);
    window.addEventListener('resize', this.onResize);
    this.onResize();
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
    if (this.motion.matches) this.draw(true);
    else this.frame = requestAnimationFrame(this.animate);
  }

  animate(timestamp) {
    this.frame = null;
    if (this.destroyed || document.hidden || this.motion.matches) return;
    const dt = this.lastTime === null ? 1 / 60 : Math.min((timestamp - this.lastTime) / 1000, 1 / 30);
    this.lastTime = timestamp;
    this.phase += dt * 3;
    this.audioLevel += (this.targetLevel - this.audioLevel) * (1 - Math.exp(-dt * 9));
    this.draw(false);
    this.frame = requestAnimationFrame(this.animate);
  }

  draw(staticFrame) {
    const ctx = this.ctx;
    const { width, height } = this;
    if (!width || !height) return;
    ctx.clearRect(0, 0, width, height);
    const stroke = ctx.createLinearGradient(0, 0, width, 0);
    stroke.addColorStop(0, 'rgba(164,181,255,0)');
    stroke.addColorStop(0.25, 'rgba(164,181,255,0.65)');
    stroke.addColorStop(0.75, 'rgba(139,221,231,0.65)');
    stroke.addColorStop(1, 'rgba(139,221,231,0)');
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= 100; i++) {
      const progress = i / 100;
      const envelope = Math.sin(progress * Math.PI) ** 2;
      const amplitude = staticFrame ? 0 : 0.8 + this.audioLevel * height * 0.38;
      const wave = Math.sin(progress * 15 - this.phase) * 0.7 + Math.sin(progress * 27 + this.phase * 0.8) * 0.3;
      const x = width * progress;
      const y = height / 2 + wave * amplitude * envelope;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  destroy() {
    if (!this.ctx || this.destroyed) return;
    this.destroyed = true;
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.observer.disconnect();
    document.removeEventListener('visibilitychange', this.onVisibility);
    this.motion.removeEventListener('change', this.onMotion);
    window.removeEventListener('resize', this.onResize);
  }
}
window.AudioWaveform = AudioWaveform;

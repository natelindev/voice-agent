/**
 * Live Audio Waveform / Oscilloscope using HTML5 Canvas
 * Displays a sleek, rolling multi-harmonic audio wave.
 */

class AudioWaveform {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.audioLevel = 0.0;
    this.targetLevel = 0.0;
    this.phase = 0;
    this.points = 80;

    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  setAudioLevel(level) {
    this.targetLevel = Math.max(0.0, Math.min(1.0, level));
  }

  animate() {
    this.phase += 0.08;
    this.audioLevel += (this.targetLevel - this.audioLevel) * 0.2;

    const width = this.canvas.width;
    const height = this.canvas.height;
    const centerY = height / 2;

    this.ctx.clearRect(0, 0, width, height);

    // Baseline amplitude + reactive audio amplitude
    const amp = Math.max(2, this.audioLevel * (height * 0.42));

    this.ctx.save();

    // Outer glow pass
    this.ctx.beginPath();
    for (let i = 0; i <= this.points; i++) {
      const x = (i / this.points) * width;
      // Window function (fade wave at the edges)
      const windowing = Math.sin((i / this.points) * Math.PI);
      const y = centerY + (
        Math.sin(i * 0.18 + this.phase) * 0.65 +
        Math.cos(i * 0.32 - this.phase * 0.8) * 0.35
      ) * amp * windowing;

      if (i === 0) {
        this.ctx.moveTo(x, y);
      } else {
        this.ctx.lineTo(x, y);
      }
    }
    this.ctx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
    this.ctx.lineWidth = 4;
    this.ctx.stroke();

    // Inner sharp pass
    this.ctx.beginPath();
    for (let i = 0; i <= this.points; i++) {
      const x = (i / this.points) * width;
      const windowing = Math.sin((i / this.points) * Math.PI);
      const y = centerY + (
        Math.sin(i * 0.18 + this.phase) * 0.65 +
        Math.cos(i * 0.32 - this.phase * 0.8) * 0.35
      ) * amp * windowing;

      if (i === 0) {
        this.ctx.moveTo(x, y);
      } else {
        this.ctx.lineTo(x, y);
      }
    }
    this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.85)';
    this.ctx.lineWidth = 1.5;
    this.ctx.stroke();

    this.ctx.restore();

    requestAnimationFrame(this.animate);
  }
}

window.AudioWaveform = AudioWaveform;

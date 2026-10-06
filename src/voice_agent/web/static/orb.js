/**
 * Animated Glowing Voice Orb using HTML5 Canvas
 * Reacts to pipeline states (listening, thinking, speaking) and live audio RMS.
 */

class VoiceOrb {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.state = 'listening';
    this.audioLevel = 0.0;
    this.targetLevel = 0.0;
    this.time = 0;

    // Palette per state
    this.palettes = {
      listening: {
        core: [56, 189, 248],      // cyan-400
        mid: [99, 102, 241],       // indigo-500
        outer: [129, 140, 248],    // indigo-400
        speed: 0.02,
        baseRadius: 0.28,
        pulseScale: 0.04
      },
      speech_detected: {
        core: [52, 211, 153],      // emerald-400
        mid: [56, 189, 248],       // cyan-400
        outer: [99, 102, 241],
        speed: 0.035,
        baseRadius: 0.32,
        pulseScale: 0.08
      },
      transcribing: {
        core: [251, 191, 36],      // amber-400
        mid: [245, 158, 11],       // amber-500
        outer: [217, 119, 6],
        speed: 0.04,
        baseRadius: 0.29,
        pulseScale: 0.05
      },
      thinking: {
        core: [168, 85, 247],      // purple-500
        mid: [236, 72, 153],       // pink-500
        outer: [99, 102, 241],
        speed: 0.05,
        baseRadius: 0.30,
        pulseScale: 0.06
      },
      speaking: {
        core: [6, 182, 212],       // cyan-500
        mid: [59, 130, 246],       // blue-500
        outer: [139, 92, 246],     // violet-500
        speed: 0.045,
        baseRadius: 0.33,
        pulseScale: 0.16
      },
      interrupted: {
        core: [244, 63, 94],       // rose-500
        mid: [225, 29, 72],
        outer: [159, 18, 57],
        speed: 0.06,
        baseRadius: 0.26,
        pulseScale: 0.03
      }
    };

    this.particles = [];
    this.initParticles();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  initParticles() {
    this.particles = [];
    for (let i = 0; i < 32; i++) {
      this.particles.push({
        angle: (i / 32) * Math.PI * 2,
        distance: 0.32 + Math.random() * 0.12,
        speed: 0.005 + Math.random() * 0.01,
        radius: 1.5 + Math.random() * 2,
        alpha: 0.2 + Math.random() * 0.5
      });
    }
  }

  setState(newState) {
    this.state = newState;
  }

  setAudioLevel(level) {
    this.targetLevel = Math.max(0.0, Math.min(1.0, level));
  }

  animate() {
    this.time += 1;
    // Smooth interpolation towards target audio level
    this.audioLevel += (this.targetLevel - this.audioLevel) * 0.25;

    const width = this.canvas.width;
    const height = this.canvas.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const minDim = Math.min(width, height);

    this.ctx.clearRect(0, 0, width, height);

    const cfg = this.palettes[this.state] || this.palettes.listening;

    // Harmonic breathing pulse
    const harmonic = Math.sin(this.time * cfg.speed) * cfg.pulseScale;
    const audioExpansion = this.audioLevel * 0.22;
    const currentRadius = minDim * (cfg.baseRadius + harmonic + audioExpansion);

    // Multi-layer organic glow
    this.drawGlowLayers(centerX, centerY, currentRadius, cfg);

    // Dynamic wave ripples (prominent when speaking or listening to audio)
    if (this.state === 'speaking' || this.audioLevel > 0.08) {
      this.drawRipples(centerX, centerY, currentRadius, cfg);
    }

    // Thinking orbital ring
    if (this.state === 'thinking') {
      this.drawThinkingRings(centerX, centerY, currentRadius, cfg);
    }

    // Ambient floating particles
    this.drawParticles(centerX, centerY, minDim, cfg);

    requestAnimationFrame(this.animate);
  }

  drawGlowLayers(cx, cy, radius, cfg) {
    const ctx = this.ctx;
    ctx.save();

    // Outer aura
    const outerGrad = ctx.createRadialGradient(cx, cy, radius * 0.2, cx, cy, radius * 1.8);
    outerGrad.addColorStop(0, `rgba(${cfg.outer.join(',')}, 0.25)`);
    outerGrad.addColorStop(0.6, `rgba(${cfg.mid.join(',')}, 0.08)`);
    outerGrad.addColorStop(1, 'rgba(0,0,0,0)');

    ctx.fillStyle = outerGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 1.8, 0, Math.PI * 2);
    ctx.fill();

    // Mid body
    const midGrad = ctx.createRadialGradient(cx, cy, radius * 0.1, cx, cy, radius);
    midGrad.addColorStop(0, `rgba(${cfg.core.join(',')}, 0.85)`);
    midGrad.addColorStop(0.5, `rgba(${cfg.mid.join(',')}, 0.65)`);
    midGrad.addColorStop(1, `rgba(${cfg.outer.join(',')}, 0.1)`);

    ctx.fillStyle = midGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fill();

    // Inner bright core
    const coreRadius = radius * 0.45;
    const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreRadius);
    coreGrad.addColorStop(0, 'rgba(255, 255, 255, 0.95)');
    coreGrad.addColorStop(0.4, `rgba(${cfg.core.join(',')}, 0.8)`);
    coreGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');

    ctx.fillStyle = coreGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, coreRadius, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  drawRipples(cx, cy, radius, cfg) {
    const ctx = this.ctx;
    ctx.save();
    const count = 3;
    for (let i = 0; i < count; i++) {
      const offset = (this.time * 0.03 + (i / count)) % 1;
      const rippleR = radius * (1 + offset * 0.55);
      const alpha = (1 - offset) * 0.35 * Math.min(1.0, this.audioLevel * 2 + 0.3);

      ctx.strokeStyle = `rgba(${cfg.core.join(',')}, ${alpha})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(cx, cy, rippleR, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  drawThinkingRings(cx, cy, radius, cfg) {
    const ctx = this.ctx;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.time * 0.04);

    ctx.strokeStyle = `rgba(${cfg.outer.join(',')}, 0.45)`;
    ctx.lineWidth = 2;
    ctx.setLineDash([12, 16]);

    ctx.beginPath();
    ctx.arc(0, 0, radius * 1.25, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();
  }

  drawParticles(cx, cy, minDim, cfg) {
    const ctx = this.ctx;
    ctx.save();
    for (const p of this.particles) {
      p.angle += p.speed;
      const dist = minDim * p.distance;
      const px = cx + Math.cos(p.angle) * dist;
      const py = cy + Math.sin(p.angle) * dist;

      ctx.fillStyle = `rgba(${cfg.core.join(',')}, ${p.alpha})`;
      ctx.beginPath();
      ctx.arc(px, py, p.radius, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }
}

window.VoiceOrb = VoiceOrb;

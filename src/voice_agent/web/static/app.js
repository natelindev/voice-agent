/**
 * Main application client controller for Voice Agent Web Companion.
 * Connects via WebSocket, manages state, chat cards, and interactive controls.
 */

(function () {
  'use strict';

  // DOM Elements
  const connectionDot = document.getElementById('connectionDot');
  const connectionLabel = document.getElementById('connectionLabel');
  const app = document.querySelector('.app-container');
  const steps = document.querySelectorAll('[data-step]');
  const statusPill = document.getElementById('statusPill');
  const statusText = document.getElementById('statusText');
  const stateHeadline = document.getElementById('stateHeadline');
  const stateSubtext = document.getElementById('stateSubtext');
  const chatFeed = document.getElementById('chatFeed');
  const emptyState = document.getElementById('emptyState');
  const turnCount = document.getElementById('turnCount');
  const meterFill = document.getElementById('meterFill');
  const meterValue = document.getElementById('meterValue');
  const inputMeter = document.getElementById('inputMeter');
  const meterLabel = document.getElementById('meterLabel');
  const muteBtn = document.getElementById('muteBtn');
  const muteLabel = document.getElementById('muteLabel');
  const interruptBtn = document.getElementById('interruptBtn');
  const clearBtn = document.getElementById('clearBtn');
  const latencyDisplay = document.getElementById('latencyDisplay');

  // Visualizers
  const particles = new VoiceParticles('particleCanvas');
  const waveform = new AudioWaveform('waveformCanvas');

  // State
  let ws = null;
  let isMuted = false;
  let totalTurns = 0;
  let activeAssistantCard = null;
  let reconnectAttempts = 0;
  let currentState = 'idle';
  let currentMessage = '';
  let backend = 'api';

  const i18n = window.VoiceI18n;
  const t = (key, values) => i18n.t(key, values);
  const states = ['idle', 'listening', 'speech_detected', 'transcribing', 'thinking', 'speaking', 'interrupted'];
  let connectionPhase = 'connecting';
  let lastLatency = null;

  function formatTime(date) {
    return date.toLocaleTimeString(i18n.language === 'zh' ? 'zh-CN' : 'en-US',
      { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function renderTurnCount() {
    turnCount.textContent = t(totalTurns === 1 ? 'turn.one' : 'turn.many', { count: totalTurns });
  }

  function renderBackend() {
    const labels = backend === 'demo'
      ? [t('backend.preview'), t('backend.simulated')]
      : backend === 'local' ? [t('backend.local'), 'Codex'] : [t('backend.api'), 'Coral'];
    document.getElementById('backendTags').replaceChildren(...labels.map(label => {
      const tag = document.createElement('span');
      tag.className = 'tag';
      tag.textContent = label;
      return tag;
    }));
  }

  // --- WebSocket Connection ---
  function connectWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      reconnectAttempts = 0;
      connectionDot.classList.remove('disconnected');
      connectionPhase = 'connected';
      connectionLabel.textContent = t('connection.connected');
      muteBtn.disabled = false;
      interruptBtn.disabled = false;
      renderState();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
      } catch (err) {
        console.error('Failed to parse WebSocket packet:', err);
      }
    };

    ws.onclose = () => {
      connectionDot.classList.add('disconnected');
      connectionPhase = 'offline';
      connectionLabel.textContent = t('connection.offline');
      muteBtn.disabled = true;
      interruptBtn.disabled = true;
      app.dataset.state = 'idle';
      statusPill.dataset.state = 'idle';
      renderState();
      particles.setState('idle');
      handleAudioLevel(0);
      steps.forEach(step => step.removeAttribute('aria-current'));
      const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts++), 5000);
      setTimeout(connectWebSocket, delay);
    };

    ws.onerror = (err) => {
      console.warn('WebSocket error:', err);
      ws.close();
    };
  }

  // --- Event Dispatcher ---
  function handleServerEvent(event) {
    switch (event.event_type) {
      case 'audio_level':
        handleAudioLevel(event.level, event.peak);
        break;

      case 'state_change':
        if (event.backend) {
          backend = event.backend;
          renderBackend();
        }
        if (typeof event.is_muted === 'boolean') updateMuteUI(event.is_muted);
        handleStateChange(event.state, event.message);
        break;

      case 'transcript':
        handleTranscript(event.role, event.text, event.is_final);
        break;

      case 'token_delta':
        handleTokenDelta(event.delta);
        break;

      case 'turn_metrics':
        handleTurnMetrics(event);
        break;

      case 'control_command':
        if (event.action === 'mute') updateMuteUI(true);
        if (event.action === 'unmute') updateMuteUI(false);
        break;

      default:
        break;
    }
  }

  // --- Audio Level ---
  function handleAudioLevel(level, peak) {
    level = Number.isFinite(level) ? Math.max(0, Math.min(1, level)) : 0;
    particles.setAudioLevel(level);
    waveform.setAudioLevel(level);

    const pct = Math.round(level * 100);
    meterFill.style.width = `${pct}%`;
    meterValue.textContent = `${pct}%`;
    inputMeter.setAttribute('aria-valuenow', pct);
  }

  // --- State Changes ---
  function handleStateChange(state, customMessage) {
    currentState = state;
    currentMessage = customMessage || '';
    particles.setState(state);
    statusPill.setAttribute('data-state', state);
    app.dataset.state = state;

    const activeStep = {
      listening: 'listen', speech_detected: 'listen',
      transcribing: 'understand', thinking: 'think', speaking: 'speak',
    }[state];
    steps.forEach(step => {
      if (step.dataset.step === activeStep) step.setAttribute('aria-current', 'step');
      else step.removeAttribute('aria-current');
    });
    renderState();
  }

  function renderState() {
    const state = currentState;
    if (connectionPhase !== 'connected') {
      const prefix = connectionPhase === 'offline' ? 'offline' : 'initial';
      stateHeadline.textContent = t(`${prefix}.headline`);
      stateSubtext.textContent = t(`${prefix}.subtext`);
      statusText.textContent = t(connectionPhase === 'offline' ? 'status.reconnecting' : 'connection.connecting');
      return;
    }
    const safeState = states.includes(state) ? state : 'idle';
    const micOff = isMuted && ['idle', 'listening', 'speech_detected'].includes(state);
    if (micOff) {
      stateHeadline.textContent = t('muted.headline');
      stateSubtext.textContent = t('muted.subtext');
      statusText.textContent = t('status.muted');
      return;
    }
    stateHeadline.textContent = t(`state.${safeState}.headline`);
    // Keep actionable server errors visible; routine pipeline detail stays in logs.
    const isError = /\b(error|failed|unavailable|unable|denied|timed out)\b/i.test(currentMessage);
    stateSubtext.textContent = isError ? currentMessage : t(`state.${safeState}.subtext`);
    if (backend === 'demo' && !isError) {
      stateSubtext.textContent = state === 'listening' || state === 'idle'
        ? t('preview.subtext') : t(`state.${safeState}.subtext`);
    }
    statusText.textContent = t(`status.${safeState}`);
  }

  // --- Transcripts & Chat Feed ---
  function handleTranscript(role, text, isFinal) {
    if (!text || !text.trim()) return;

    if (emptyState) {
      emptyState.style.display = 'none';
    }

    const timestamp = new Date();
    const timeStr = formatTime(timestamp);

    if (role === 'user') {
      const card = document.createElement('div');
      card.className = 'chat-card user';
      card.innerHTML = `
        <div class="card-header">
          <span class="card-role" data-i18n="role.user">${t('role.user')}</span>
          <span class="card-time" data-time="${timestamp.toISOString()}">${timeStr}</span>
        </div>
        <div class="card-body">${escapeHtml(text)}</div>
      `;
      chatFeed.appendChild(card);
      activeAssistantCard = null;
      totalTurns++;
      renderTurnCount();
    } else if (role === 'assistant') {
      if (activeAssistantCard) {
        activeAssistantCard.querySelector('.card-body').textContent = text;
      } else {
        const card = document.createElement('div');
        card.className = 'chat-card assistant';
        card.innerHTML = `
          <div class="card-header">
            <span class="card-role" data-i18n="role.assistant">${t('role.assistant')}</span>
            <span class="card-time" data-time="${timestamp.toISOString()}">${timeStr}</span>
          </div>
          <div class="card-body">${escapeHtml(text)}</div>
          <div class="card-footer"></div>
        `;
        chatFeed.appendChild(card);
        activeAssistantCard = card;
      }
    }

    scrollChatToBottom();
  }

  function handleTokenDelta(delta) {
    if (emptyState) {
      emptyState.style.display = 'none';
    }

    const timestamp = new Date();
    const timeStr = formatTime(timestamp);

    if (!activeAssistantCard) {
      const card = document.createElement('div');
      card.className = 'chat-card assistant';
      card.innerHTML = `
        <div class="card-header">
          <span class="card-role" data-i18n="role.assistant">${t('role.assistant')}</span>
          <span class="card-time" data-time="${timestamp.toISOString()}">${timeStr}</span>
        </div>
        <div class="card-body">${escapeHtml(delta)}</div>
        <div class="card-footer"></div>
      `;
      chatFeed.appendChild(card);
      activeAssistantCard = card;
    } else {
      const body = activeAssistantCard.querySelector('.card-body');
      body.textContent += delta;
    }

    scrollChatToBottom();
  }

  function handleTurnMetrics(metrics) {
    lastLatency = metrics.total_seconds;
    const badgeText = formatLatencyBadge(lastLatency);
    latencyDisplay.textContent = t('latency.value', { seconds: lastLatency.toFixed(2) });

    if (activeAssistantCard) {
      const footer = activeAssistantCard.querySelector('.card-footer');
      if (footer) {
        footer.innerHTML = `<span class="metrics-badge" data-seconds="${lastLatency}">${badgeText}</span>`;
      }
    }
    activeAssistantCard = null;
  }

  function scrollChatToBottom() {
    chatFeed.scrollTop = chatFeed.scrollHeight;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // --- Controls & Outbound Messages ---
  function sendCommand(action, payload = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action, payload }));
    }
  }

  function toggleMute() {
    if (muteBtn.disabled) return;
    isMuted = !isMuted;
    sendCommand(isMuted ? 'mute' : 'unmute');
    updateMuteUI(isMuted);
  }

  function updateMuteUI(muted) {
    isMuted = muted;
    muteLabel.textContent = t(isMuted ? 'unmute.label' : 'mute.label');
    muteBtn.setAttribute('aria-pressed', String(isMuted));
    muteBtn.setAttribute('aria-label', t(isMuted ? 'unmute.aria' : 'mute.aria'));
    app.dataset.muted = String(isMuted);
    meterLabel.textContent = t(isMuted ? 'mic.muted' : 'mic.label');
    if (isMuted) handleAudioLevel(0);
    renderState();
  }

  function interruptPlayback() {
    sendCommand('interrupt');
  }

  function clearHistory() {
    sendCommand('clear_history');
    emptyState.style.display = '';
    chatFeed.replaceChildren(emptyState);
    totalTurns = 0;
    renderTurnCount();
    activeAssistantCard = null;
    lastLatency = null;
    latencyDisplay.textContent = '—';
  }

  // Event Listeners
  muteBtn.addEventListener('click', toggleMute);
  interruptBtn.addEventListener('click', interruptPlayback);
  clearBtn.addEventListener('click', clearHistory);

  // Global Keyboard Shortcuts
  window.addEventListener('keydown', (e) => {
    if (e.repeat || e.metaKey || e.ctrlKey || e.altKey ||
        e.target.closest('input, textarea, select, button, a, [contenteditable="true"]')) return;

    if (e.key === ' ' || e.code === 'Space') {
      e.preventDefault();
      interruptPlayback();
    } else if (e.key === 'm' || e.key === 'M') {
      toggleMute();
    } else if (e.key === 'r' || e.key === 'R') {
      clearHistory();
    }
  });

  function formatLatencyBadge(seconds) {
    return `${t(backend === 'demo' ? 'response.demo' : 'response.normal')} · ${t('latency.value', { seconds: seconds.toFixed(2) })}`;
  }

  function renderLanguage() {
    connectionLabel.textContent = t(`connection.${connectionPhase === 'offline' ? 'offline' : connectionPhase}`);
    renderBackend();
    renderTurnCount();
    updateMuteUI(isMuted);
    latencyDisplay.textContent = lastLatency === null ? '—' : t('latency.value', { seconds: lastLatency.toFixed(2) });
    document.querySelectorAll('.card-time[data-time]').forEach(element => {
      element.textContent = formatTime(new Date(element.dataset.time));
    });
    document.querySelectorAll('.metrics-badge[data-seconds]').forEach(element => {
      element.textContent = formatLatencyBadge(Number(element.dataset.seconds));
    });
  }
  window.addEventListener('languagechange', renderLanguage);

  // Initialize
  renderLanguage();
  connectWebSocket();
})();

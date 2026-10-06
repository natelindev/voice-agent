/**
 * Main application client controller for Voice Agent Web Companion.
 * Connects via WebSocket, manages state, chat cards, and interactive controls.
 */

(function () {
  'use strict';

  // DOM Elements
  const connectionDot = document.getElementById('connectionDot');
  const statusPill = document.getElementById('statusPill');
  const statusText = document.getElementById('statusText');
  const stateHeadline = document.getElementById('stateHeadline');
  const stateSubtext = document.getElementById('stateSubtext');
  const chatFeed = document.getElementById('chatFeed');
  const emptyState = document.getElementById('emptyState');
  const turnCount = document.getElementById('turnCount');
  const meterFill = document.getElementById('meterFill');
  const meterValue = document.getElementById('meterValue');
  const muteBtn = document.getElementById('muteBtn');
  const muteLabel = document.getElementById('muteLabel');
  const interruptBtn = document.getElementById('interruptBtn');
  const clearBtn = document.getElementById('clearBtn');
  const latencyDisplay = document.getElementById('latencyDisplay');

  // Visualizers
  const orb = new VoiceOrb('orbCanvas');
  const waveform = new AudioWaveform('waveformCanvas');

  // State
  let ws = null;
  let isMuted = false;
  let totalTurns = 0;
  let activeAssistantCard = null;
  let reconnectAttempts = 0;

  // Friendly state titles and descriptions
  const stateDescriptions = {
    listening: {
      headline: 'Listening...',
      subtext: 'Speak into your microphone naturally. Barge-in is active.'
    },
    speech_detected: {
      headline: 'Listening...',
      subtext: 'Speech detected. Processing audio input...'
    },
    transcribing: {
      headline: 'Transcribing...',
      subtext: 'Converting speech to text via Whisper API...'
    },
    thinking: {
      headline: 'Thinking...',
      subtext: 'Generating streaming response with GPT-4o-mini...'
    },
    speaking: {
      headline: 'Speaking...',
      subtext: 'Streaming natural voice playback via TTS. Speak to interrupt.'
    },
    interrupted: {
      headline: 'Interrupted',
      subtext: 'Barge-in triggered. Playback cancelled, listening to you.'
    },
    idle: {
      headline: 'Ready',
      subtext: 'Microphone is active.'
    }
  };

  // --- WebSocket Connection ---
  function connectWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      reconnectAttempts = 0;
      connectionDot.classList.remove('disconnected');
      statusText.textContent = 'Connected';
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
      statusText.textContent = 'Reconnecting...';
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
    orb.setAudioLevel(level);
    waveform.setAudioLevel(level);

    const pct = Math.round(level * 100);
    meterFill.style.width = `${pct}%`;
    meterValue.textContent = `${pct}%`;
  }

  // --- State Changes ---
  function handleStateChange(state, customMessage) {
    orb.setState(state);
    statusPill.setAttribute('data-state', state);

    const desc = stateDescriptions[state] || stateDescriptions.idle;
    stateHeadline.textContent = desc.headline;
    stateSubtext.textContent = customMessage || desc.subtext;
    statusText.textContent = state.toUpperCase();
  }

  // --- Transcripts & Chat Feed ---
  function handleTranscript(role, text, isFinal) {
    if (!text || !text.trim()) return;

    if (emptyState) {
      emptyState.style.display = 'none';
    }

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    if (role === 'user') {
      const card = document.createElement('div');
      card.className = 'chat-card user';
      card.innerHTML = `
        <div class="card-header">
          <span class="card-role">You</span>
          <span class="card-time">${timeStr}</span>
        </div>
        <div class="card-body">${escapeHtml(text)}</div>
      `;
      chatFeed.appendChild(card);
      activeAssistantCard = null;
      totalTurns++;
      turnCount.textContent = `${totalTurns} turn${totalTurns === 1 ? '' : 's'}`;
    } else if (role === 'assistant') {
      if (activeAssistantCard) {
        activeAssistantCard.querySelector('.card-body').textContent = text;
      } else {
        const card = document.createElement('div');
        card.className = 'chat-card assistant';
        card.innerHTML = `
          <div class="card-header">
            <span class="card-role">Agent</span>
            <span class="card-time">${timeStr}</span>
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

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    if (!activeAssistantCard) {
      const card = document.createElement('div');
      card.className = 'chat-card assistant';
      card.innerHTML = `
        <div class="card-header">
          <span class="card-role">Agent</span>
          <span class="card-time">${timeStr}</span>
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
    const totalMs = Math.round(metrics.total_seconds * 1000);
    const asrMs = Math.round(metrics.asr_seconds * 1000);
    const ttftMs = Math.round(metrics.ttft_seconds * 1000);

    const badgeText = `ASR: ${asrMs}ms · TTFT: ${ttftMs}ms · Total: ${metrics.total_seconds.toFixed(2)}s`;
    latencyDisplay.textContent = `${metrics.total_seconds.toFixed(2)}s`;

    if (activeAssistantCard) {
      const footer = activeAssistantCard.querySelector('.card-footer');
      if (footer) {
        footer.innerHTML = `<span class="metrics-badge">${badgeText}</span>`;
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
    isMuted = !isMuted;
    sendCommand(isMuted ? 'mute' : 'unmute');
    updateMuteUI(isMuted);
  }

  function updateMuteUI(muted) {
    isMuted = muted;
    muteLabel.textContent = isMuted ? 'Unmute' : 'Mute';
    if (isMuted) {
      muteBtn.style.backgroundColor = 'rgba(244, 63, 94, 0.2)';
    } else {
      muteBtn.style.backgroundColor = '';
    }
  }

  function interruptPlayback() {
    sendCommand('interrupt');
  }

  function clearHistory() {
    sendCommand('clear_history');
    chatFeed.innerHTML = `
      <div class="empty-state" id="emptyState">
        <div class="empty-icon">🎙️</div>
        <p>Your conversation history will appear here in real time.</p>
      </div>
    `;
    totalTurns = 0;
    turnCount.textContent = '0 turns';
    activeAssistantCard = null;
    latencyDisplay.textContent = '—';
  }

  // Event Listeners
  muteBtn.addEventListener('click', toggleMute);
  interruptBtn.addEventListener('click', interruptPlayback);
  clearBtn.addEventListener('click', clearHistory);

  // Global Keyboard Shortcuts
  window.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === ' ' || e.code === 'Space') {
      e.preventDefault();
      interruptPlayback();
    } else if (e.key === 'm' || e.key === 'M') {
      toggleMute();
    } else if (e.key === 'r' || e.key === 'R') {
      clearHistory();
    }
  });

  // Initialize
  connectWebSocket();
})();

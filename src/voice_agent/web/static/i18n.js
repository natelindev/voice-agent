/** English and Simplified Chinese UI copy; conversation content stays untouched. */
(function () {
  'use strict';
  const messages = {
    en: {
      'page.title': 'Voice Agent — Real-time Assistant',
      'brand.caption': 'REALTIME ASSISTANT',
      'session.label': 'VOICE SESSION', 'session.aria': 'Voice session',
      'connection.connecting': 'Connecting', 'connection.connected': 'Connected', 'connection.offline': 'Offline',
      'initial.headline': 'A little closer.', 'initial.subtext': 'Connecting to your voice session.',
      'offline.headline': 'A moment apart.', 'offline.subtext': 'Reconnecting to your voice session.',
      'status.reconnecting': 'Reconnecting', 'status.muted': 'Muted',
      'status.idle': 'Ready', 'status.listening': 'Listening', 'status.speech_detected': 'Listening',
      'status.transcribing': 'Understanding', 'status.thinking': 'Thinking', 'status.speaking': 'Speaking', 'status.interrupted': 'Your turn',
      'state.idle.headline': 'Let’s talk.', 'state.idle.subtext': 'A thought, a question, a place to start.',
      'state.listening.headline': 'Listening.', 'state.listening.subtext': 'Take your time. I’m here when you’re ready.',
      'state.speech_detected.headline': 'I’m with you.', 'state.speech_detected.subtext': 'Keep going. I’m listening to your thoughts.',
      'state.transcribing.headline': 'Understanding.', 'state.transcribing.subtext': 'Putting your words together.',
      'state.thinking.headline': 'Thinking.', 'state.thinking.subtext': 'A moment to find the right words.',
      'state.speaking.headline': 'Speaking.', 'state.speaking.subtext': 'Press Interrupt whenever you want to take the lead.',
      'state.interrupted.headline': 'Your turn.', 'state.interrupted.subtext': 'Response paused. What’s on your mind?',
      'muted.headline': 'Microphone off.', 'muted.subtext': 'Unmute whenever you’re ready.',
      'preview.subtext': 'A simulated conversation. Explore the controls below.',
      'flow.aria': 'Conversation stages', 'flow.listen': 'Listen', 'flow.understand': 'Understand', 'flow.think': 'Think', 'flow.speak': 'Speak',
      'conversation.label': 'CONVERSATION', 'conversation.aria': 'Conversation', 'transcript.aria': 'Conversation transcript',
      'empty.title': 'A space for your thoughts.', 'empty.subtext': 'Start speaking. Your conversation will take shape here.',
      'conversation.note': 'Every turn, in one place.', 'turn.one': '{count} turn', 'turn.many': '{count} turns',
      'clear.aria': 'Clear conversation', 'clear.title': 'Clear conversation (R)',
      'mic.label': 'MIC INPUT', 'mic.muted': 'MIC MUTED', 'mic.aria': 'Microphone input level',
      'mute.label': 'Mute', 'unmute.label': 'Unmute', 'mute.aria': 'Mute microphone', 'unmute.aria': 'Unmute microphone', 'mute.title': 'Toggle mute (M)',
      'interrupt.label': 'Interrupt', 'interrupt.aria': 'Interrupt assistant', 'interrupt.title': 'Interrupt assistant (Space)',
      'latency.label': 'RESPONSE TIME', 'latency.value': '{seconds}s',
      'role.user': 'You', 'role.assistant': 'Agent', 'response.normal': 'Response', 'response.demo': 'Simulated response',
      'backend.preview': 'Preview mode', 'backend.simulated': 'Simulated session', 'backend.local': 'Mac speech', 'backend.api': 'Voice session',
    },
    zh: {
      'page.title': 'Voice Agent — 实时语音助手',
      'brand.caption': '实时语音助手',
      'session.label': '语音会话', 'session.aria': '语音会话',
      'connection.connecting': '连接中', 'connection.connected': '已连接', 'connection.offline': '未连接',
      'initial.headline': '即将连接。', 'initial.subtext': '正在连接你的语音会话。',
      'offline.headline': '稍等片刻。', 'offline.subtext': '正在重新连接语音会话。',
      'status.reconnecting': '重新连接中', 'status.muted': '已静音',
      'status.idle': '准备就绪', 'status.listening': '聆听中', 'status.speech_detected': '聆听中',
      'status.transcribing': '理解中', 'status.thinking': '思考中', 'status.speaking': '回应中', 'status.interrupted': '轮到你了',
      'state.idle.headline': '聊聊吧。', 'state.idle.subtext': '一个想法、一个问题，都可以作为开始。',
      'state.listening.headline': '我在听。', 'state.listening.subtext': '慢慢说，准备好了就开始。',
      'state.speech_detected.headline': '我在这里。', 'state.speech_detected.subtext': '继续说，我在认真听你的想法。',
      'state.transcribing.headline': '理解中。', 'state.transcribing.subtext': '正在整理你说的话。',
      'state.thinking.headline': '思考中。', 'state.thinking.subtext': '给我一点时间，组织合适的回应。',
      'state.speaking.headline': '回应中。', 'state.speaking.subtext': '想接着说时，随时点击「打断」。',
      'state.interrupted.headline': '轮到你了。', 'state.interrupted.subtext': '已暂停回应。你想说些什么？',
      'muted.headline': '麦克风已关闭。', 'muted.subtext': '准备好了，随时取消静音。',
      'preview.subtext': '这是模拟对话，你可以体验下方的控制按钮。',
      'flow.aria': '对话阶段', 'flow.listen': '聆听', 'flow.understand': '理解', 'flow.think': '思考', 'flow.speak': '回应',
      'conversation.label': '对话记录', 'conversation.aria': '对话', 'transcript.aria': '对话文字记录',
      'empty.title': '留给思绪的一方空间。', 'empty.subtext': '开始说话，让对话在这里展开。',
      'conversation.note': '每一轮对话，都在这里。', 'turn.one': '{count} 轮对话', 'turn.many': '{count} 轮对话',
      'clear.aria': '清空对话', 'clear.title': '清空对话（R）',
      'mic.label': '麦克风输入', 'mic.muted': '麦克风已静音', 'mic.aria': '麦克风输入音量',
      'mute.label': '静音', 'unmute.label': '取消静音', 'mute.aria': '关闭麦克风', 'unmute.aria': '开启麦克风', 'mute.title': '切换静音（M）',
      'interrupt.label': '打断', 'interrupt.aria': '打断助手回应', 'interrupt.title': '打断助手回应（空格）',
      'latency.label': '回应耗时', 'latency.value': '{seconds} 秒',
      'role.user': '你', 'role.assistant': '助手', 'response.normal': '回应耗时', 'response.demo': '模拟回应',
      'backend.preview': '预览模式', 'backend.simulated': '模拟会话', 'backend.local': 'Mac 语音', 'backend.api': '语音会话',
    },
  };
  let saved;
  try { saved = localStorage.getItem('voice-agent-language'); } catch {}
  let language = ['en', 'zh'].includes(saved) ? saved : (navigator.language || 'en').toLowerCase().startsWith('zh') ? 'zh' : 'en';
  function t(key, params = {}) {
    const value = messages[language][key] ?? messages.en[key] ?? key;
    return value.replace(/\{(\w+)\}/g, (match, name) => params[name] === undefined ? match : String(params[name]));
  }
  function apply() {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    document.title = t('page.title');
    document.querySelectorAll('[data-i18n]').forEach(element => {
      element.textContent = t(element.dataset.i18n);
    });
    for (const attr of ['aria-label', 'title']) {
      document.querySelectorAll(`[data-i18n-${attr}]`).forEach(element => {
        element.setAttribute(attr, t(element.getAttribute(`data-i18n-${attr}`)));
      });
    }
    const toggle = document.getElementById('languageToggle');
    if (toggle) {
      toggle.textContent = language === 'zh' ? 'English' : '中文';
      toggle.lang = language === 'zh' ? 'en' : 'zh-CN';
      toggle.setAttribute('aria-label', language === 'zh' ? 'Switch to English' : '切换为中文');
    }
  }
  function setLanguage(value) {
    language = value === 'zh' ? 'zh' : 'en';
    try { localStorage.setItem('voice-agent-language', language); } catch {}
    apply();
    window.dispatchEvent(new CustomEvent('languagechange', { detail: language }));
  }
  window.VoiceI18n = { t, setLanguage, get language() { return language; }, messages };
  apply();
  document.getElementById('languageToggle')?.addEventListener('click', () => setLanguage(language === 'zh' ? 'en' : 'zh'));
})();

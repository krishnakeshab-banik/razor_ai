let voicesReady = false;

function ensureVoices() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return [];
  const voices = window.speechSynthesis.getVoices();
  if (voices.length) voicesReady = true;
  return voices;
}

if (typeof window !== 'undefined' && window.speechSynthesis) {
  window.speechSynthesis.onvoiceschanged = () => {
    voicesReady = true;
  };
}

function whenVoicesReady(callback) {
  const existing = ensureVoices();
  if (existing.length) {
    callback(existing);
    return;
  }
  const finish = () => callback(ensureVoices());
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    finish();
    return;
  }
  const onChange = () => {
    window.speechSynthesis.removeEventListener('voiceschanged', onChange);
    finish();
  };
  window.speechSynthesis.addEventListener('voiceschanged', onChange);
  window.setTimeout(() => {
    window.speechSynthesis.removeEventListener('voiceschanged', onChange);
    finish();
  }, 400);
}

function scoreEnglishVoice(voice) {
  const label = `${voice.name} ${voice.lang}`.toLowerCase();
  let score = 0;
  if (/neural|natural|online|premium|wavenet|studio|enhanced/.test(label)) score += 60;
  if (/google/.test(label)) score += 45;
  if (/aria|jenny|sonia|natasha|sara|guy|ryan|andrew|emma|jane|neerja|prabhat/.test(label)) score += 40;
  if (/en-in/.test(label)) score += 22;
  if (/en-gb/.test(label)) score += 16;
  if (/en-us/.test(label)) score += 14;
  if (voice.localService === false) score += 10;
  if (/desktop|david|mark|zira|hazel|sam\b/.test(label)) score -= 40;
  return score;
}

function pickVoice(voices, locale) {
  if (locale === 'hi') {
    return voices.find((voice) => voice.lang && voice.lang.toLowerCase().startsWith('hi')) || null;
  }
  const english = voices.filter((voice) => voice.lang && /^en\b/i.test(voice.lang.replace('_', '-')));
  if (!english.length) return null;
  return [...english].sort((a, b) => scoreEnglishVoice(b) - scoreEnglishVoice(a))[0];
}

function humanizeEnglish(text) {
  return String(text || '')
    .replace(/₹/g, 'rupees ')
    .replace(/\bGMV\b/g, 'G M V')
    .replace(/\bUTR\b/g, 'U T R')
    .replace(/\bGST\b/g, 'G S T')
    .replace(/\bMID\b/g, 'M I D')
    .replace(/\bT\+2\b/g, 'T plus 2')
    .replace(/[—–]/g, '. ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function stopSpeech() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
}

export function speakText(text, locale = 'en') {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  const raw = String(text || '').replace(/\s+/g, ' ').trim();
  if (!raw) return;
  stopSpeech();
  const clean = locale === 'hi' ? raw : humanizeEnglish(raw);
  whenVoicesReady((voices) => {
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.lang = locale === 'hi' ? 'hi-IN' : 'en-IN';
    if (locale === 'hi') {
      utterance.rate = 0.95;
      utterance.pitch = 1;
    } else {
      utterance.rate = 0.92;
      utterance.pitch = 1.04;
    }
    const match = pickVoice(voices, locale);
    if (match) {
      utterance.voice = match;
      if (match.lang) utterance.lang = match.lang;
    }
    window.speechSynthesis.speak(utterance);
  });
}

export function speechSupported() {
  return typeof window !== 'undefined' && Boolean(window.speechSynthesis);
}

export { voicesReady };

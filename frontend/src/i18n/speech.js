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

export function stopSpeech() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
}

export function speakText(text, locale = 'en') {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  const clean = String(text || '').replace(/\s+/g, ' ').trim();
  if (!clean) return;
  stopSpeech();
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.lang = locale === 'hi' ? 'hi-IN' : 'en-IN';
  utterance.rate = locale === 'hi' ? 0.95 : 1;
  const prefix = locale === 'hi' ? 'hi' : 'en';
  const voices = ensureVoices();
  const match = voices.find((voice) => voice.lang && voice.lang.toLowerCase().startsWith(prefix));
  if (match) utterance.voice = match;
  window.speechSynthesis.speak(utterance);
}

export function speechSupported() {
  return typeof window !== 'undefined' && Boolean(window.speechSynthesis);
}

export { voicesReady };

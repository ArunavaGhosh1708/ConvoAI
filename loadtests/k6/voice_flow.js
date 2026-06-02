/**
 * k6 load test — voice pipeline (transcribe → chat → synthesize).
 *
 * Run:
 *   k6 run --env BASE_URL=http://localhost:8000 \
 *           --env API_KEY=dev-api-key \
 *           loadtests/k6/voice_flow.js
 */

import { check, sleep } from 'k6';
import http from 'k6/http';
import { Trend, Rate } from 'k6/metrics';
import encoding from 'k6/encoding';

import { BASE_URL, CHAT_HEADERS, THRESHOLDS } from './config.js';

const transcribeLatency = new Trend('voice_transcribe_ms', true);
const synthesizeLatency = new Trend('voice_synthesize_ms', true);
const voiceErrorRate    = new Rate('voice_errors');

export const options = {
  scenarios: {
    voice_load: {
      executor:  'constant-arrival-rate',
      rate:       20,           // 20 voice flows / second
      timeUnit:  '1s',
      duration:  '60s',
      preAllocatedVUs: 50,
      maxVUs:    100,
    },
  },
  thresholds: {
    ...THRESHOLDS,
    voice_transcribe_ms: ['p(95)<3000'],  // STT < 3 s p95
    voice_synthesize_ms: ['p(95)<5000'],  // TTS < 5 s p95 (streaming)
    voice_errors:        ['rate<0.05'],   // < 5% error
  },
};

// Minimal valid WAV header (44 bytes) + silence for test audio
function makeSilentWav(durationMs = 500) {
  const sampleRate   = 16000;
  const numSamples   = Math.floor(sampleRate * durationMs / 1000);
  const dataSize     = numSamples * 2;
  const buf = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buf);

  // RIFF header
  view.setUint32(0,  0x52494646, false); // "RIFF"
  view.setUint32(4,  36 + dataSize, true);
  view.setUint32(8,  0x57415645, false); // "WAVE"
  view.setUint32(12, 0x666d7420, false); // "fmt "
  view.setUint32(16, 16, true);           // PCM chunk size
  view.setUint16(20, 1, true);            // PCM format
  view.setUint16(22, 1, true);            // 1 channel
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  view.setUint32(36, 0x64617461, false);  // "data"
  view.setUint32(40, dataSize, true);
  // Samples remain zero (silence)

  const bytes = new Uint8Array(buf);
  return encoding.b64encode(bytes);
}

export default function () {
  const sessionId = `k6-voice-${__VU}-${__ITER}`;

  // ── 1. Transcribe ────────────────────────────────────────────────────────
  const wavB64  = makeSilentWav();
  const wavBytes = encoding.b64decode(wavB64, 'std', 'b');

  const formData = {
    audio: http.file(wavBytes, 'recording.wav', 'audio/wav'),
  };

  const t0 = Date.now();
  const txRes = http.post(`${BASE_URL}/api/v1/voice/transcribe`, formData, {
    headers: { 'X-API-Key': CHAT_HEADERS['X-API-Key'] },
    timeout: '15s',
    tags:    { endpoint: 'transcribe' },
  });
  transcribeLatency.add(Date.now() - t0);

  const txOk = check(txRes, {
    'transcribe 200': (r) => r.status === 200,
    'has text field': (r) => {
      try { return !!JSON.parse(r.body).text; } catch { return false; }
    },
  });

  if (!txOk) {
    voiceErrorRate.add(1);
    return;
  }

  const transcript = JSON.parse(txRes.body).text || 'What is your return policy?';

  // ── 2. Chat (JSON, not streaming) ────────────────────────────────────────
  const chatRes = http.post(
    `${BASE_URL}/api/v1/chat`,
    JSON.stringify({ session_id: sessionId, message: transcript, stream: false, channel: 'voice' }),
    { headers: CHAT_HEADERS, timeout: '15s', tags: { endpoint: 'chat' } },
  );

  check(chatRes, { 'chat 200': (r) => r.status === 200 });
  const chatText = (() => {
    try { return JSON.parse(chatRes.body).response || ''; } catch { return ''; }
  })();

  // ── 3. Synthesize ────────────────────────────────────────────────────────
  const t1 = Date.now();
  const ttsRes = http.post(
    `${BASE_URL}/api/v1/voice/synthesize`,
    JSON.stringify({ text: chatText.slice(0, 200) || 'Thank you for contacting us.' }),
    { headers: CHAT_HEADERS, responseType: 'binary', timeout: '20s', tags: { endpoint: 'synthesize' } },
  );
  synthesizeLatency.add(Date.now() - t1);

  const ttsOk = check(ttsRes, {
    'synthesize 200': (r) => r.status === 200,
    'audio bytes received': (r) => r.body && r.body.length > 0,
  });

  voiceErrorRate.add(ttsOk ? 0 : 1);

  sleep(1);
}

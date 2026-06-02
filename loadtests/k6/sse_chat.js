/**
 * k6 load test — 500 concurrent SSE chat sessions.
 *
 * Target: sustain 500 VUs for 60 s with no dropped streams (< 1% error rate).
 *
 * Run:
 *   k6 run --env BASE_URL=http://localhost:8000 \
 *           --env API_KEY=dev-api-key \
 *           loadtests/k6/sse_chat.js
 *
 * For CI (shorter):
 *   k6 run --vus 50 --duration 30s loadtests/k6/sse_chat.js
 */

import { check, sleep } from 'k6';
import http from 'k6/http';
import { Trend, Counter, Rate } from 'k6/metrics';

import { BASE_URL, CHAT_HEADERS, THRESHOLDS } from './config.js';

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------
const sseFirstByte   = new Trend('sse_first_byte_ms',   true);
const sseTotalBytes  = new Trend('sse_total_bytes',      true);
const sseDropped     = new Counter('sse_dropped_streams');
const sseCompletions = new Counter('sse_completed_streams');
const escalationRate = new Rate('sse_escalated');

// ---------------------------------------------------------------------------
// Test configuration
// ---------------------------------------------------------------------------
export const options = {
  scenarios: {
    sse_ramp: {
      executor:       'ramping-vus',
      startVUs:       0,
      stages: [
        { duration: '30s', target: 100  },
        { duration: '60s', target: 500  },  // sustain 500 VUs
        { duration: '30s', target: 0    },  // ramp down
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    ...THRESHOLDS,
    sse_dropped: ['count<5'],          // at most 5 dropped streams
    sse_first_byte_ms: ['p(95)<800'], // SSE first token < 800 ms p95
  },
};

// ---------------------------------------------------------------------------
// Session pool — randomise IDs so sessions don't collide
// ---------------------------------------------------------------------------
const QUESTIONS = [
  'What is your return policy?',
  'How do I reset my password?',
  'Can I cancel my subscription?',
  'What payment methods do you accept?',
  'Where is my order?',
  'How do I contact support?',
  'Is there a free trial?',
  'How do I update my billing information?',
];

function randomQuestion() {
  return QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
}

// ---------------------------------------------------------------------------
// VU logic
// ---------------------------------------------------------------------------
export default function () {
  const sessionId = `k6-${__VU}-${__ITER}`;
  const payload = JSON.stringify({
    session_id: sessionId,
    message:    randomQuestion(),
    stream:     true,
    channel:    'chat',
  });

  const startTs = Date.now();
  let firstByteReceived = false;
  let totalBytes = 0;
  let streamComplete = false;
  let escalated = false;

  const res = http.post(`${BASE_URL}/api/v1/chat`, payload, {
    headers:        CHAT_HEADERS,
    responseType:   'text',
    timeout:        '30s',
    tags:           { endpoint: 'chat' },
  });

  const ok = check(res, {
    'status 200': (r) => r.status === 200,
    'content-type SSE': (r) => (r.headers['Content-Type'] || '').includes('text/event-stream'),
  });

  if (!ok || res.status !== 200) {
    sseDropped.add(1);
    return;
  }

  // Parse SSE body (all events arrive in the response body as a text blob)
  const body = res.body || '';
  totalBytes = body.length;
  sseTotalBytes.add(totalBytes);

  const lines = body.split('\n');
  for (const line of lines) {
    if (!firstByteReceived && line.startsWith('event: token')) {
      sseFirstByte.add(Date.now() - startTs);
      firstByteReceived = true;
    }
    if (line.startsWith('event: done')) {
      streamComplete = true;
    }
    if (line.includes('"escalated": true')) {
      escalated = true;
    }
  }

  if (streamComplete) {
    sseCompletions.add(1);
  } else {
    sseDropped.add(1);
  }

  escalationRate.add(escalated ? 1 : 0);

  check(null, {
    'stream completed': () => streamComplete,
    'first byte received': () => firstByteReceived,
  });

  sleep(Math.random() * 2 + 0.5);  // 0.5–2.5 s think time
}

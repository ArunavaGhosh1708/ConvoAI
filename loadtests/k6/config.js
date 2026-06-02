/**
 * Shared k6 configuration for ConvoAI load tests.
 * Override via environment variables:
 *   BASE_URL   default http://localhost:8000
 *   API_KEY    default dev-api-key
 *   ADMIN_JWT  default (empty — set for admin endpoints)
 */

export const BASE_URL  = __ENV.BASE_URL  || 'http://localhost:8000';
export const API_KEY   = __ENV.API_KEY   || 'dev-api-key';
export const ADMIN_JWT = __ENV.ADMIN_JWT || '';

export const CHAT_HEADERS = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
};

export const ADMIN_HEADERS = {
  'Content-Type': 'application/json',
  Authorization: `Bearer ${ADMIN_JWT}`,
};

// Standard thresholds shared across scenarios
export const THRESHOLDS = {
  http_req_failed:          ['rate<0.01'],          // < 1% error rate
  http_req_duration:        ['p(95)<2000'],          // 95th pct < 2 s
  'http_req_duration{endpoint:chat}': ['p(99)<5000'], // chat may be slower
};

// wsClient.js
import { MockWebSocket } from './MockWebSocket'  // your class file
export function makeWS(url, useMock = false) {
  if (useMock) return new MockWebSocket(url);
  return new WebSocket(url);
}

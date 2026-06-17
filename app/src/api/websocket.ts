/**
 * WebSocket Client for MYiot Real-Time Updates
 * 
 * Connects to the backend WebSocket endpoint and provides:
 * - Auto-reconnect with exponential backoff
 * - Message subscription system
 * - Connection status callbacks
 */

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;

type WsStatus = 'connecting' | 'connected' | 'disconnected';
type MessageHandler = (data: Record<string, unknown>) => void;

class WsClient {
  private ws: WebSocket | null = null;
  private status: WsStatus = 'disconnected';
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private handlers: Set<MessageHandler> = new Set();
  private statusHandlers: Set<(status: WsStatus) => void> = new Set();
  private shouldReconnect = true;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) return;
    this.shouldReconnect = true;
    this.setStatus('connecting');

    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        this.setStatus('connected');
        this.reconnectDelay = 1000;
        // Subscribe to all device state changes (no device_type filter)
        this.send({ action: 'subscribe' });
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong') return;
          this.handlers.forEach(h => h(data));
        } catch { /* ignore parse errors */ }
      };

      this.ws.onclose = () => {
        this.setStatus('disconnected');
        this.ws = null;
        if (this.shouldReconnect) this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.ws?.close();
      };
    } catch {
      this.setStatus('disconnected');
      this.scheduleReconnect();
    }
  }

  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null; }
    this.ws?.close();
    this.ws = null;
    this.setStatus('disconnected');
  }

  send(data: Record<string, unknown>) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  onMessage(handler: MessageHandler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  onStatusChange(handler: (status: WsStatus) => void) {
    this.statusHandlers.add(handler);
    handler(this.status); // Immediate current status
    return () => this.statusHandlers.delete(handler);
  }

  getStatus() { return this.status; }

  private setStatus(s: WsStatus) {
    this.status = s;
    this.statusHandlers.forEach(h => h(s));
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.shouldReconnect) this.connect();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
  }
}

export const wsClient = new WsClient();
export type { WsStatus };

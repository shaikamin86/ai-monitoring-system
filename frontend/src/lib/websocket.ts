import { WSMessage } from "@/types";

type MessageHandler = (msg: WSMessage) => void;

class WSClient {
  private ws: WebSocket | null = null;
  private handlers: Set<MessageHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private reconnectDelay = 2000;
  private url: string;
  private mounted = true;

  constructor(url: string) {
    this.url = url;
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    try {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = () => {
        this.reconnectDelay = 2000;
        this.pingInterval = setInterval(() => {
          this.ws?.readyState === WebSocket.OPEN &&
            this.ws.send(JSON.stringify({ type: "ping" }));
        }, 10000);
      };
      this.ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          this.handlers.forEach((h) => h(msg));
        } catch {}
      };
      this.ws.onclose = () => {
        if (this.pingInterval) clearInterval(this.pingInterval);
        if (this.mounted) this._scheduleReconnect();
      };
      this.ws.onerror = () => this.ws?.close();
    } catch {}
  }

  private _scheduleReconnect() {
    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, 30000);
      this.connect();
    }, this.reconnectDelay);
  }

  subscribe(handler: MessageHandler) {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  disconnect() {
    this.mounted = false;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.pingInterval) clearInterval(this.pingInterval);
    this.ws?.close();
  }
}

let _client: WSClient | null = null;

export function getWSClient(): WSClient {
  if (!_client) {
    const url = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/ws`;
    _client = new WSClient(url);
    _client.connect();
  }
  return _client;
}

/**
 * HTTP API Client for MYiot Backend
 * 
 * All endpoints are relative — the backend serves both API and static files
 * from the same origin. When the backend is unavailable, operations fail
 * gracefully and the UI falls back to local state.
 */

const API_BASE = ''; // Same-origin

interface ApiResponse<T> {
  data?: T;
  error?: string;
  ok: boolean;
}

async function req<T>(path: string, opts?: RequestInit): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...opts?.headers },
      ...opts,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      return { ok: false, error: `${res.status}: ${text}` };
    }
    const contentType = res.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      return { ok: true, data: await res.json() as T };
    }
    return { ok: true, data: await res.text() as T };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'Network error' };
  }
}

export const api = {
  // Devices
  listDevices: () => req<any[]>('/api/devices'),
  getDevice: (id: string) => req<any>(`/api/devices/${id}`),
  sendCommand: (id: string, payload: Record<string, unknown>) => req<any>(`/api/devices/${id}/command`, { method: 'POST', body: JSON.stringify(payload) }),
  removeDevice: (id: string) => req<void>(`/api/devices/${id}`, { method: 'DELETE' }),
  addManual: (config: Record<string, unknown>) => req<any>('/api/devices/manual', { method: 'POST', body: JSON.stringify(config) }),

  // Manufacturers
  listManufacturers: () => req<Record<string, any>>('/api/manufacturers'),

  // Camera streams
  getMjpegUrl: (cameraId: string) => `/api/cameras/${cameraId}/mjpeg`,
  getSnapshotUrl: (cameraId: string) => `/api/cameras/${cameraId}/snapshot`,
  sendWebRtcOffer: (cameraId: string, sdp: string) => req<{ type: string; sdp: string }>(`/api/cameras/${cameraId}/webrtc`, {
    method: 'POST',
    body: JSON.stringify({ sdp, type: 'offer' }),
  }),

  // Logs
  getLogs: (limit = 50, offset = 0) => req<any[]>(`/api/logs?limit=${limit}&offset=${offset}`),

  // Health
  health: () => req<{ status: string; devices_registered: number }>('/health'),
};

export type { ApiResponse };

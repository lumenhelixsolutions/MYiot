import type { Device, DeviceType, ThermoMode } from '@/types';

export interface BackendDeviceState {
  device_id: string;
  manufacturer: string;
  model: string;
  device_type: DeviceType;
  online: boolean;
  state: Record<string, unknown>;
  last_updated: number;
}

export function mapDeviceState(state: BackendDeviceState): Device {
  const s = state.state || {};
  return {
    id: state.device_id,
    name: (s.name as string) || state.device_id,
    manufacturer: state.manufacturer,
    model: state.model,
    type: state.device_type,
    room: (s.room as string) || 'Unknown',
    online: state.online,
    power: s.power === undefined ? true : Boolean(s.power),
    brightness: s.brightness as number | undefined,
    color: (s.color as string) || undefined,
    colorTemp: s.color_temp as number | undefined,
    targetTemp: s.target_temp as number | undefined,
    currentTemp: s.current_temp as number | undefined,
    humidity: s.humidity as number | undefined,
    mode: (s.mode as ThermoMode) || undefined,
    streamUrl: (s.stream_url as string) || undefined,
    ipAddress: (s.ip_address as string) || (s.ip as string) || '',
    protocol: String(s.protocol || 'REST').toUpperCase(),
    signalStrength: (s.signal_strength as number) || 0,
    lastSeen: state.last_updated * 1000 || Date.now(),
    firmware: (s.firmware as string) || 'unknown',
  };
}

export function mapDeviceStates(states: BackendDeviceState[]): Device[] {
  return states.map(mapDeviceState);
}

/** Normalize WebSocket state_change payloads from the hub. */
export function mapWsStateChange(msg: Record<string, unknown>): Device | null {
  const raw = (msg.state as BackendDeviceState | undefined)
    ?? ({
      device_id: msg.device_id,
      manufacturer: '',
      model: '',
      device_type: 'plug',
      online: true,
      state: {},
      last_updated: Date.now() / 1000,
    } as BackendDeviceState);

  if (!raw?.device_id && !msg.device_id) return null;

  const normalized: BackendDeviceState = {
    ...raw,
    device_id: String(raw.device_id || msg.device_id),
  };
  return mapDeviceState(normalized);
}

export interface BackendDiscoveredDevice {
  id: string;
  device_id: string;
  name: string;
  manufacturer: string;
  manufacturer_key?: string;
  model?: string;
  type: DeviceType;
  device_type?: DeviceType;
  ip_address: string;
  protocol: string;
  mac_address?: string;
  firmware?: string;
  signal_strength: number;
  scan_phase: string;
  stream_url?: string;
}

export function mapDiscoveredDevice(raw: BackendDiscoveredDevice) {
  const type = (raw.type || raw.device_type || 'plug') as DeviceType;
  return {
    id: raw.id || raw.device_id,
    name: raw.name,
    manufacturer: raw.manufacturer,
    type,
    ipAddress: raw.ip_address,
    protocol: raw.protocol,
    signalStrength: raw.signal_strength ?? 0,
    scanPhase: (raw.scan_phase || 'probing') as import('@/types').ScanPhase,
    macAddress: raw.mac_address || '',
    firmware: raw.firmware || 'unknown',
    streamUrl: raw.stream_url,
  };
}

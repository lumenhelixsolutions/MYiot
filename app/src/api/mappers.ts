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

export type DeviceType = 'plug' | 'light' | 'thermostat' | 'camera';
export type ThermoMode = 'off' | 'heat' | 'cool' | 'auto' | 'eco';
export type RecordingMode = 'Off' | 'Events' | 'Continuous';
export type AlertType = 'motion' | 'sound' | 'offline' | 'zone_breach';
export type AlertSeverity = 'info' | 'warning' | 'critical';
export type CameraLayout = '1x1' | '2x2' | '3x3' | '1+2' | '2+1';
export type ScanPhase = 'idle' | 'probing' | 'authenticating' | 'classifying' | 'complete';

export interface Point { x: number; y: number; }

export interface Zone {
  id: string;
  cameraId: string;
  name: string;
  points: Point[];
  color: string;
  motionEnabled: boolean;
  sensitivity: number;
  lastTriggered?: number;
  triggerCount: number;
}

export interface CameraAlert {
  id: string;
  cameraId: string;
  zoneId?: string;
  type: AlertType;
  severity: AlertSeverity;
  message: string;
  timestamp: number;
  acknowledged: boolean;
  snapshot?: string;
}

export interface AlertRule {
  id: string;
  cameraId: string;
  type: AlertType;
  enabled: boolean;
  sensitivity: number;
  cooldownSeconds: number;
  notifyPush: boolean;
  notifyEmail: boolean;
  soundEnabled: boolean;
}

export interface CameraPreset {
  id: string;
  name: string;
  pan: number;
  tilt: number;
  zoom: number;
}

export interface CameraRecording {
  id: string;
  cameraId: string;
  startTime: number;
  endTime?: number;
  triggeredBy: 'manual' | 'motion' | 'schedule';
  sizeMB: number;
}

export interface Device {
  id: string;
  name: string;
  manufacturer: string;
  model: string;
  type: DeviceType;
  room: string;
  online: boolean;
  power: boolean;
  brightness?: number;
  color?: string;
  colorTemp?: number;
  targetTemp?: number;
  currentTemp?: number;
  humidity?: number;
  mode?: ThermoMode;
  streamUrl?: string;
  ipAddress: string;
  protocol: string;
  signalStrength: number;
  lastSeen: number;
  firmware: string;
}

export interface ActivityEvent {
  id: string;
  timestamp: number;
  type: 'power_on' | 'power_off' | 'temperature' | 'motion' | 'connection' | 'automation' | 'error' | 'discovery' | 'auth' | 'zone_breach' | 'alert_triggered';
  deviceId: string;
  deviceName: string;
  manufacturer: string;
  description: string;
  details?: Record<string, unknown>;
}

export interface Room {
  id: string;
  name: string;
  deviceCount: number;
  activeCount: number;
  gradient: string;
}

export interface ManufacturerConfig {
  key: string;
  name: string;
  protocol: string;
  authType: string;
  deviceTypes: DeviceType[];
  port?: number;
  enabled: boolean;
}

export interface Credential {
  id: string;
  manufacturer: string;
  authType: string;
  username?: string;
  token?: string;
  apiKey?: string;
  lastUsed?: number;
}

export interface DiscoveredDevice {
  id: string;
  name: string;
  manufacturer: string;
  type: DeviceType;
  ipAddress: string;
  protocol: string;
  signalStrength: number;
  scanPhase: ScanPhase;
  macAddress?: string;
  firmware?: string;
}

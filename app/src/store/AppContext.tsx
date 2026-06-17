import React, { createContext, useContext, useReducer, useCallback } from 'react';
import type {
  Device, DeviceType, ActivityEvent, Room, ManufacturerConfig, Credential,
  Zone, CameraAlert, AlertRule, CameraPreset, CameraRecording,
  DiscoveredDevice, ScanPhase,
} from '@/types';
import { api } from '@/api/client';
import { useBackendSync } from './useBackendSync';
import type { BackendState } from './useBackendSync';

/* ─── Seed Data ─── */

const seedDevices: Device[] = [
  { id: 'cam-1', name: 'Front Door', manufacturer: 'Ring', model: 'Video Doorbell Pro 2', type: 'camera', room: 'Entry', online: true, power: true, streamUrl: 'rtsp://192.168.1.101:554/live', ipAddress: '192.168.1.101', protocol: 'REST', signalStrength: 92, lastSeen: Date.now(), firmware: '1.18.0' },
  { id: 'cam-2', name: 'Backyard', manufacturer: 'Wyze', model: 'Cam v3', type: 'camera', room: 'Garden', online: true, power: true, streamUrl: 'rtsp://192.168.1.102:554/live', ipAddress: '192.168.1.102', protocol: 'REST', signalStrength: 78, lastSeen: Date.now(), firmware: '4.36.11' },
  { id: 'cam-3', name: 'Garage', manufacturer: 'EOOEIES', model: 'OS-PTZ4K', type: 'camera', room: 'Garage', online: true, power: true, streamUrl: 'rtsp://192.168.1.103:554/live', ipAddress: '192.168.1.103', protocol: 'REST', signalStrength: 85, lastSeen: Date.now(), firmware: '3.1.2' },
  { id: 'cam-4', name: 'Living Room', manufacturer: 'Nest', model: 'Cam Indoor', type: 'camera', room: 'Living Room', online: true, power: true, streamUrl: 'rtsp://192.168.1.104:554/live', ipAddress: '192.168.1.104', protocol: 'REST', signalStrength: 95, lastSeen: Date.now(), firmware: '2.4.1' },
  { id: 'cam-5', name: 'Driveway', manufacturer: 'Ring', model: 'Stick Up Cam Pro', type: 'camera', room: 'Driveway', online: false, power: false, streamUrl: 'rtsp://192.168.1.105:554/live', ipAddress: '192.168.1.105', protocol: 'REST', signalStrength: 0, lastSeen: Date.now() - 7200000, firmware: '1.15.0' },
  { id: 'hue-1', name: 'Living Room Ceiling', manufacturer: 'Philips Hue', model: 'White & Color A19', type: 'light', room: 'Living Room', online: true, power: true, brightness: 85, color: '#6366F1', colorTemp: 3500, ipAddress: '192.168.1.106', protocol: 'REST', signalStrength: 92, lastSeen: Date.now(), firmware: '1.104.2' },
  { id: 'hue-2', name: 'Bedside Lamp', manufacturer: 'Philips Hue', model: 'White Ambiance', type: 'light', room: 'Bedroom', online: true, power: false, brightness: 40, color: '#fbbf24', colorTemp: 2700, ipAddress: '192.168.1.107', protocol: 'REST', signalStrength: 78, lastSeen: Date.now(), firmware: '1.104.2' },
  { id: 'kasa-1', name: 'Coffee Maker', manufacturer: 'TP-Link Kasa', model: 'KP125', type: 'plug', room: 'Kitchen', online: true, power: true, ipAddress: '192.168.1.108', protocol: 'TCP', signalStrength: 88, lastSeen: Date.now(), firmware: '1.0.20' },
  { id: 'kasa-2', name: 'Office Desk', manufacturer: 'TP-Link Kasa', model: 'KP115', type: 'plug', room: 'Office', online: true, power: true, ipAddress: '192.168.1.109', protocol: 'TCP', signalStrength: 95, lastSeen: Date.now(), firmware: '1.0.18' },
  { id: 'nest-1', name: 'Hallway Thermostat', manufacturer: 'Nest', model: 'Learning Gen 4', type: 'thermostat', room: 'Hallway', online: true, power: true, targetTemp: 72, currentTemp: 70, humidity: 45, mode: 'auto', ipAddress: '192.168.1.110', protocol: 'REST', signalStrength: 85, lastSeen: Date.now(), firmware: '5.9.4' },
  { id: 'nest-2', name: 'Upstairs', manufacturer: 'Nest', model: 'Thermostat E', type: 'thermostat', room: 'Upstairs', online: true, power: true, targetTemp: 68, currentTemp: 69, humidity: 42, mode: 'cool', ipAddress: '192.168.1.111', protocol: 'REST', signalStrength: 80, lastSeen: Date.now(), firmware: '5.9.2' },
  { id: 'lifx-1', name: 'Kitchen Strip', manufacturer: 'LIFX', model: 'Beam', type: 'light', room: 'Kitchen', online: true, power: true, brightness: 70, color: '#10b981', colorTemp: 4000, ipAddress: '192.168.1.112', protocol: 'REST', signalStrength: 86, lastSeen: Date.now(), firmware: '3.90' },
  { id: 'ikea-1', name: 'Desk Lamp', manufacturer: 'IKEA Tradfri', model: 'LED1837R5', type: 'light', room: 'Office', online: true, power: false, brightness: 60, color: '#f8fafc', colorTemp: 3000, ipAddress: '192.168.1.113', protocol: 'CoAP', signalStrength: 76, lastSeen: Date.now(), firmware: '2.3.080' },
  { id: 'ecobee-1', name: 'Master Bedroom', manufacturer: 'Ecobee', model: 'SmartThermostat', type: 'thermostat', room: 'Master Bedroom', online: false, power: false, targetTemp: 70, currentTemp: 68, humidity: 50, mode: 'off', ipAddress: '192.168.1.114', protocol: 'REST', signalStrength: 0, lastSeen: Date.now() - 3600000, firmware: '4.8.7' },
  { id: 'wemo-1', name: 'Living Room Outlet', manufacturer: 'Wemo', model: 'Mini Smart Plug', type: 'plug', room: 'Living Room', online: true, power: false, ipAddress: '192.168.1.115', protocol: 'SOAP', signalStrength: 82, lastSeen: Date.now(), firmware: 'WeMo_WW_2.00' },
  { id: 'govee-1', name: 'TV Backlight', manufacturer: 'Govee', model: 'Immersion T2', type: 'light', room: 'Living Room', online: true, power: true, brightness: 55, color: '#a855f7', colorTemp: 5000, ipAddress: '192.168.1.116', protocol: 'REST', signalStrength: 91, lastSeen: Date.now(), firmware: '1.08.02' },
  { id: 'hue-3', name: 'Porch Light', manufacturer: 'Philips Hue', model: 'White PAR38', type: 'light', room: 'Outdoor', online: true, power: false, brightness: 100, color: '#f1f5f9', colorTemp: 4000, ipAddress: '192.168.1.117', protocol: 'REST', signalStrength: 65, lastSeen: Date.now(), firmware: '1.104.2' },
  { id: 'kasa-3', name: 'Bedroom Charger', manufacturer: 'TP-Link Kasa', model: 'EP10', type: 'plug', room: 'Bedroom', online: true, power: false, ipAddress: '192.168.1.118', protocol: 'TCP', signalStrength: 79, lastSeen: Date.now(), firmware: '1.0.15' },
  { id: 'sonoff-1', name: 'Garden Lights', manufacturer: 'Sonoff', model: 'MINIR4', type: 'plug', room: 'Outdoor', online: true, power: true, ipAddress: '192.168.1.119', protocol: 'REST', signalStrength: 58, lastSeen: Date.now(), firmware: '1.4.0' },
];

const seedZones: Zone[] = [
  { id: 'z1', cameraId: 'cam-1', name: 'Walkway', points: [{ x: 10, y: 40 }, { x: 50, y: 40 }, { x: 50, y: 90 }, { x: 10, y: 90 }], color: '#10b981', motionEnabled: true, sensitivity: 75, lastTriggered: Date.now() - 300000, triggerCount: 12 },
  { id: 'z2', cameraId: 'cam-1', name: 'Porch', points: [{ x: 55, y: 30 }, { x: 95, y: 30 }, { x: 95, y: 70 }, { x: 55, y: 70 }], color: '#f59e0b', motionEnabled: true, sensitivity: 60, lastTriggered: Date.now() - 900000, triggerCount: 5 },
  { id: 'z3', cameraId: 'cam-2', name: 'Patio', points: [{ x: 15, y: 20 }, { x: 85, y: 20 }, { x: 85, y: 80 }, { x: 15, y: 80 }], color: '#6366f1', motionEnabled: true, sensitivity: 80, lastTriggered: Date.now() - 600000, triggerCount: 8 },
  { id: 'z4', cameraId: 'cam-3', name: 'Entry', points: [{ x: 20, y: 30 }, { x: 80, y: 30 }, { x: 80, y: 85 }, { x: 20, y: 85 }], color: '#ef4444', motionEnabled: true, sensitivity: 70, triggerCount: 3 },
  { id: 'z5', cameraId: 'cam-4', name: 'Sofa Area', points: [{ x: 10, y: 35 }, { x: 60, y: 35 }, { x: 60, y: 90 }, { x: 10, y: 90 }], color: '#06b6d4', motionEnabled: false, sensitivity: 50, triggerCount: 0 },
];

const seedAlerts: CameraAlert[] = [
  { id: 'a1', cameraId: 'cam-1', zoneId: 'z1', type: 'motion', severity: 'warning', message: 'Motion detected in Walkway zone', timestamp: Date.now() - 300000, acknowledged: false },
  { id: 'a2', cameraId: 'cam-2', zoneId: 'z3', type: 'motion', severity: 'info', message: 'Motion detected in Patio zone', timestamp: Date.now() - 600000, acknowledged: true },
  { id: 'a3', cameraId: 'cam-1', type: 'motion', severity: 'warning', message: 'Person detected at front door', timestamp: Date.now() - 900000, acknowledged: true },
  { id: 'a4', cameraId: 'cam-5', type: 'offline', severity: 'critical', message: 'Driveway camera went offline', timestamp: Date.now() - 7200000, acknowledged: false },
  { id: 'a5', cameraId: 'cam-3', zoneId: 'z4', type: 'zone_breach', severity: 'warning', message: 'Zone breach detected in Entry', timestamp: Date.now() - 1200000, acknowledged: true },
];

const seedAlertRules: AlertRule[] = [
  { id: 'r1', cameraId: 'cam-1', type: 'motion', enabled: true, sensitivity: 75, cooldownSeconds: 30, notifyPush: true, notifyEmail: false, soundEnabled: true },
  { id: 'r2', cameraId: 'cam-1', type: 'sound', enabled: false, sensitivity: 50, cooldownSeconds: 60, notifyPush: false, notifyEmail: false, soundEnabled: false },
  { id: 'r3', cameraId: 'cam-1', type: 'offline', enabled: true, sensitivity: 100, cooldownSeconds: 0, notifyPush: true, notifyEmail: true, soundEnabled: true },
  { id: 'r4', cameraId: 'cam-2', type: 'motion', enabled: true, sensitivity: 80, cooldownSeconds: 30, notifyPush: true, notifyEmail: false, soundEnabled: false },
  { id: 'r5', cameraId: 'cam-2', type: 'offline', enabled: true, sensitivity: 100, cooldownSeconds: 0, notifyPush: true, notifyEmail: false, soundEnabled: true },
  { id: 'r6', cameraId: 'cam-3', type: 'motion', enabled: true, sensitivity: 70, cooldownSeconds: 45, notifyPush: false, notifyEmail: true, soundEnabled: true },
  { id: 'r7', cameraId: 'cam-4', type: 'motion', enabled: false, sensitivity: 60, cooldownSeconds: 30, notifyPush: false, notifyEmail: false, soundEnabled: false },
];

const seedPresets: CameraPreset[] = [
  { id: 'p1', name: 'Main View', pan: 0, tilt: 0, zoom: 1 },
  { id: 'p2', name: 'Door Close', pan: -15, tilt: 5, zoom: 2.5 },
  { id: 'p3', name: 'Wide', pan: 0, tilt: -10, zoom: 1 },
];

const seedRecordings: CameraRecording[] = [
  { id: 'rec-1', cameraId: 'cam-1', startTime: Date.now() - 3600000, endTime: Date.now() - 3540000, triggeredBy: 'motion', sizeMB: 12.4 },
  { id: 'rec-2', cameraId: 'cam-1', startTime: Date.now() - 7200000, endTime: Date.now() - 7140000, triggeredBy: 'motion', sizeMB: 8.2 },
  { id: 'rec-3', cameraId: 'cam-2', startTime: Date.now() - 1800000, triggeredBy: 'manual', sizeMB: 45.1 },
  { id: 'rec-4', cameraId: 'cam-3', startTime: Date.now() - 5400000, endTime: Date.now() - 5340000, triggeredBy: 'motion', sizeMB: 15.7 },
];

const seedEvents: ActivityEvent[] = [
  { id: 'e1', timestamp: Date.now() - 120000, type: 'zone_breach', deviceId: 'cam-1', deviceName: 'Front Door', manufacturer: 'Ring', description: 'Zone "Walkway" — motion detected', details: { zoneId: 'z1', confidence: 0.94 } },
  { id: 'e2', timestamp: Date.now() - 300000, type: 'motion', deviceId: 'cam-1', deviceName: 'Front Door', manufacturer: 'Ring', description: 'Person detected at front door', details: { confidence: 0.91 } },
  { id: 'e3', timestamp: Date.now() - 600000, type: 'motion', deviceId: 'cam-2', deviceName: 'Backyard', manufacturer: 'Wyze', description: 'Motion in Patio zone', details: { zoneId: 'z3' } },
  { id: 'e4', timestamp: Date.now() - 900000, type: 'alert_triggered', deviceId: 'cam-1', deviceName: 'Front Door', manufacturer: 'Ring', description: 'Alert rule triggered: motion', details: { ruleId: 'r1' } },
  { id: 'e5', timestamp: Date.now() - 1200000, type: 'connection', deviceId: 'cam-5', deviceName: 'Driveway', manufacturer: 'Ring', description: 'Camera went offline', details: { reason: 'connection_timeout' } },
  { id: 'e6', timestamp: Date.now() - 1800000, type: 'power_on', deviceId: 'kasa-1', deviceName: 'Coffee Maker', manufacturer: 'TP-Link Kasa', description: 'Turned ON (schedule)' },
  { id: 'e7', timestamp: Date.now() - 2400000, type: 'temperature', deviceId: 'nest-1', deviceName: 'Hallway Thermostat', manufacturer: 'Nest', description: 'Target temp changed to 72°F', details: { old: 70, new: 72 } },
  { id: 'e8', timestamp: Date.now() - 3600000, type: 'discovery', deviceId: '', deviceName: '', manufacturer: '', description: 'mDNS scan found 2 new devices' },
  { id: 'e9', timestamp: Date.now() - 5400000, type: 'motion', deviceId: 'cam-3', deviceName: 'Garage', manufacturer: 'EOOEIES', description: 'Zone breach: Entry zone', details: { zoneId: 'z4' } },
  { id: 'e10', timestamp: Date.now() - 7200000, type: 'power_off', deviceId: 'hue-2', deviceName: 'Bedside Lamp', manufacturer: 'Philips Hue', description: 'Turned OFF (sleep schedule)' },
  { id: 'e11', timestamp: Date.now() - 10800000, type: 'automation', deviceId: '', deviceName: '', manufacturer: '', description: '"Away Mode" activated — 8 devices changed' },
  { id: 'e12', timestamp: Date.now() - 14400000, type: 'motion', deviceId: 'cam-4', deviceName: 'Living Room', manufacturer: 'Nest', description: 'Motion detected (low confidence)' },
];

const seedRooms: Room[] = [
  { id: 'r1', name: 'Living Room', deviceCount: 4, activeCount: 2, gradient: 'from-indigo-500/20 to-purple-500/10' },
  { id: 'r2', name: 'Kitchen', deviceCount: 2, activeCount: 2, gradient: 'from-emerald-500/20 to-teal-500/10' },
  { id: 'r3', name: 'Bedroom', deviceCount: 3, activeCount: 1, gradient: 'from-amber-500/20 to-orange-500/10' },
  { id: 'r4', name: 'Office', deviceCount: 2, activeCount: 1, gradient: 'from-cyan-500/20 to-blue-500/10' },
  { id: 'r5', name: 'Entry', deviceCount: 1, activeCount: 1, gradient: 'from-rose-500/20 to-pink-500/10' },
];

const seedMfrs: ManufacturerConfig[] = [
  { key: 'ring', name: 'Ring', protocol: 'REST', authType: 'OAuth2', deviceTypes: ['camera'], enabled: true },
  { key: 'wyze', name: 'Wyze', protocol: 'REST', authType: 'User/Password', deviceTypes: ['camera', 'light', 'plug'], enabled: true },
  { key: 'eoeeies', name: 'EOOEIES', protocol: 'REST', authType: 'Basic Auth', deviceTypes: ['camera'], port: 80, enabled: true },
  { key: 'nest', name: 'Nest', protocol: 'REST', authType: 'OAuth2', deviceTypes: ['thermostat', 'camera'], enabled: true },
  { key: 'philips_hue', name: 'Philips Hue', protocol: 'REST', authType: 'Bridge Token', deviceTypes: ['light'], enabled: true },
  { key: 'tp_link_kasa', name: 'TP-Link Kasa', protocol: 'TCP', authType: 'None', deviceTypes: ['plug', 'light'], port: 9999, enabled: true },
  { key: 'wemo', name: 'Wemo', protocol: 'SOAP', authType: 'None', deviceTypes: ['plug'], port: 49153, enabled: true },
  { key: 'lifx', name: 'LIFX', protocol: 'REST', authType: 'Bearer Token', deviceTypes: ['light'], enabled: true },
  { key: 'govee', name: 'Govee', protocol: 'REST', authType: 'API Key', deviceTypes: ['light'], enabled: true },
  { key: 'ikea_tradfri', name: 'IKEA Tradfri', protocol: 'CoAP', authType: 'PSK', deviceTypes: ['light', 'plug'], port: 5684, enabled: true },
  { key: 'ecobee', name: 'Ecobee', protocol: 'REST', authType: 'OAuth2 PIN', deviceTypes: ['thermostat'], enabled: true },
  { key: 'sonoff', name: 'Sonoff', protocol: 'REST', authType: 'Bearer Token', deviceTypes: ['plug'], enabled: true },
  { key: 'lutron_caseta', name: 'Lutron Caseta', protocol: 'LEAP', authType: 'Certificate', deviceTypes: ['plug', 'light'], port: 8081, enabled: true },
  { key: 'meross', name: 'Meross', protocol: 'MQTT', authType: 'User/Password', deviceTypes: ['plug'], enabled: true },
  { key: 'blink', name: 'Blink', protocol: 'REST', authType: 'User/Password', deviceTypes: ['camera'], enabled: false },
  { key: 'honeywell', name: 'Honeywell', protocol: 'REST', authType: 'OAuth2', deviceTypes: ['thermostat'], enabled: false },
  { key: 'emerson_sensi', name: 'Emerson Sensi', protocol: 'REST', authType: 'OAuth2', deviceTypes: ['thermostat'], enabled: false },
  { key: 'mysa', name: 'Mysa', protocol: 'REST', authType: 'Bearer Token', deviceTypes: ['thermostat'], enabled: false },
];

const seedCreds: Credential[] = [
  { id: 'c1', manufacturer: 'Ring', authType: 'OAuth2', token: 'ring_***', lastUsed: Date.now() - 3600000 },
  { id: 'c2', manufacturer: 'Nest', authType: 'OAuth2', token: 'nest_***', lastUsed: Date.now() - 7200000 },
  { id: 'c3', manufacturer: 'Philips Hue', authType: 'Bridge Token', token: 'hue_***', lastUsed: Date.now() - 86400000 },
];

/* ─── State ─── */

interface AppState {
  devices: Device[];
  events: ActivityEvent[];
  rooms: Room[];
  manufacturers: ManufacturerConfig[];
  credentials: Credential[];
  zones: Zone[];
  alerts: CameraAlert[];
  alertRules: AlertRule[];
  presets: CameraPreset[];
  recordings: CameraRecording[];
  discoveredDevices: DiscoveredDevice[];
  searchQuery: string;
  scanActive: boolean;
}

const initialState: AppState = {
  devices: seedDevices,
  events: seedEvents,
  rooms: seedRooms,
  manufacturers: seedMfrs,
  credentials: seedCreds,
  zones: seedZones,
  alerts: seedAlerts,
  alertRules: seedAlertRules,
  presets: seedPresets,
  recordings: seedRecordings,
  discoveredDevices: [],
  searchQuery: '',
  scanActive: false,
};

/* ─── Actions ─── */

type Action =
  | { type: 'TOGGLE_DEVICE_POWER'; deviceId: string }
  | { type: 'UPDATE_DEVICE'; deviceId: string; updates: Partial<Device> }
  | { type: 'SYNC_DEVICES'; devices: Device[] }
  | { type: 'UPDATE_DEVICE_FROM_BACKEND'; deviceId: string; updates: Partial<Device> }
  | { type: 'ADD_DEVICE'; device: Device }
  | { type: 'REMOVE_DEVICE'; deviceId: string }
  | { type: 'ADD_EVENT'; event: ActivityEvent }
  | { type: 'CLEAR_EVENTS' }
  | { type: 'SET_SEARCH'; query: string }
  | { type: 'SET_SCAN_ACTIVE'; active: boolean }
  | { type: 'SET_DISCOVERED'; devices: DiscoveredDevice[] }
  | { type: 'ADD_DISCOVERED'; device: DiscoveredDevice }
  | { type: 'UPDATE_DISCOVERED'; id: string; phase: ScanPhase }
  | { type: 'ADD_ZONE'; zone: Zone }
  | { type: 'REMOVE_ZONE'; zoneId: string }
  | { type: 'UPDATE_ZONE'; zoneId: string; updates: Partial<Zone> }
  | { type: 'ADD_ALERT'; alert: CameraAlert }
  | { type: 'ACK_ALERT'; alertId: string }
  | { type: 'CLEAR_ALERTS' }
  | { type: 'ADD_RULE'; rule: AlertRule }
  | { type: 'UPDATE_RULE'; ruleId: string; updates: Partial<AlertRule> }
  | { type: 'REMOVE_RULE'; ruleId: string }
  | { type: 'ADD_RECORDING'; recording: CameraRecording }
  | { type: 'STOP_RECORDING'; recordingId: string }
  | { type: 'ADD_CREDENTIAL'; credential: Credential }
  | { type: 'REMOVE_CREDENTIAL'; credentialId: string }
  | { type: 'TOGGLE_MANUFACTURER'; key: string };

/* ─── Reducer ─── */

function appReducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'TOGGLE_DEVICE_POWER': {
      const d = state.devices.find(x => x.id === action.deviceId);
      if (!d) return state;
      const newPower = !d.power;
      return {
        ...state,
        devices: state.devices.map(x => x.id === action.deviceId ? { ...x, power: newPower, lastSeen: Date.now() } : x),
        events: [{
          id: `e-${Date.now()}`, timestamp: Date.now(),
          type: (newPower ? 'power_on' : 'power_off') as ActivityEvent['type'],
          deviceId: d.id, deviceName: d.name, manufacturer: d.manufacturer,
          description: newPower ? 'Turned ON' : 'Turned OFF',
        }, ...state.events].slice(0, 200),
      };
    }
    case 'UPDATE_DEVICE': {
      const parts: string[] = [];
      const d = state.devices.find(x => x.id === action.deviceId);
      if (!d) return state;
      if (action.updates.brightness !== undefined && action.updates.brightness !== d.brightness) parts.push(`Brightness ${action.updates.brightness}%`);
      if (action.updates.targetTemp !== undefined && action.updates.targetTemp !== d.targetTemp) parts.push(`Target ${action.updates.targetTemp}F`);
      if (action.updates.mode !== undefined && action.updates.mode !== d.mode) parts.push(`Mode ${action.updates.mode}`);
      if (action.updates.color !== undefined && action.updates.color !== d.color) parts.push('Color changed');
      const evts = parts.length > 0 ? [{
        id: `e-${Date.now()}`, timestamp: Date.now(),
        type: (action.updates.targetTemp !== undefined || action.updates.mode !== undefined ? 'temperature' : 'automation') as ActivityEvent['type'],
        deviceId: d.id, deviceName: d.name, manufacturer: d.manufacturer,
        description: parts.join(', '), details: action.updates,
      }] : [];
      return { ...state, devices: state.devices.map(x => x.id === action.deviceId ? { ...x, ...action.updates, lastSeen: Date.now() } : x), events: [...evts, ...state.events].slice(0, 200) };
    }
    case 'SYNC_DEVICES':
      return {
        ...state,
        devices: action.devices,
      };
    case 'UPDATE_DEVICE_FROM_BACKEND': {
      const exists = state.devices.find(x => x.id === action.deviceId);
      if (!exists) {
        const merged: Device = {
          id: action.deviceId,
          name: (action.updates.name as string) || action.deviceId,
          manufacturer: (action.updates.manufacturer as string) || 'unknown',
          model: (action.updates.model as string) || 'unknown',
          type: (action.updates.type as DeviceType) || 'plug',
          room: (action.updates.room as string) || 'Unknown',
          online: action.updates.online ?? true,
          power: action.updates.power ?? true,
          ipAddress: (action.updates.ipAddress as string) || '',
          protocol: (action.updates.protocol as string) || 'REST',
          signalStrength: (action.updates.signalStrength as number) || 0,
          lastSeen: action.updates.lastSeen || Date.now(),
          firmware: (action.updates.firmware as string) || 'unknown',
          ...action.updates,
        };
        return { ...state, devices: [...state.devices, merged] };
      }
      return {
        ...state,
        devices: state.devices.map(x =>
          x.id === action.deviceId ? { ...x, ...action.updates, lastSeen: Date.now() } : x
        ),
      };
    }
    case 'ADD_DEVICE': return { ...state, devices: [...state.devices, action.device], events: [{ id: `e-${Date.now()}`, timestamp: Date.now(), type: 'discovery' as ActivityEvent['type'], deviceId: action.device.id, deviceName: action.device.name, manufacturer: action.device.manufacturer, description: `Added ${action.device.name}` }, ...state.events].slice(0, 200) };
    case 'REMOVE_DEVICE': return { ...state, devices: state.devices.filter(x => x.id !== action.deviceId), events: [{ id: `e-${Date.now()}`, timestamp: Date.now(), type: 'automation' as ActivityEvent['type'], deviceId: action.deviceId, deviceName: state.devices.find(x => x.id === action.deviceId)?.name ?? '', manufacturer: state.devices.find(x => x.id === action.deviceId)?.manufacturer ?? '', description: 'Device removed' }, ...state.events].slice(0, 200) };
    case 'ADD_EVENT': return { ...state, events: [action.event, ...state.events].slice(0, 200) };
    case 'CLEAR_EVENTS': return { ...state, events: [] };
    case 'SET_SEARCH': return { ...state, searchQuery: action.query };
    case 'SET_SCAN_ACTIVE': return { ...state, scanActive: action.active };
    case 'SET_DISCOVERED': return { ...state, discoveredDevices: action.devices };
    case 'ADD_DISCOVERED': return { ...state, discoveredDevices: [...state.discoveredDevices, action.device] };
    case 'UPDATE_DISCOVERED': return { ...state, discoveredDevices: state.discoveredDevices.map(x => x.id === action.id ? { ...x, scanPhase: action.phase } : x) };
    case 'ADD_ZONE': return { ...state, zones: [...state.zones, action.zone] };
    case 'REMOVE_ZONE': return { ...state, zones: state.zones.filter(x => x.id !== action.zoneId) };
    case 'UPDATE_ZONE': return { ...state, zones: state.zones.map(x => x.id === action.zoneId ? { ...x, ...action.updates } : x) };
    case 'ADD_ALERT': return { ...state, alerts: [action.alert, ...state.alerts].slice(0, 100), events: [{ id: `e-${Date.now()}`, timestamp: Date.now(), type: 'alert_triggered' as ActivityEvent['type'], deviceId: action.alert.cameraId, deviceName: state.devices.find(x => x.id === action.alert.cameraId)?.name ?? '', manufacturer: state.devices.find(x => x.id === action.alert.cameraId)?.manufacturer ?? '', description: action.alert.message, details: { alertType: action.alert.type, severity: action.alert.severity } }, ...state.events].slice(0, 200) };
    case 'ACK_ALERT': return { ...state, alerts: state.alerts.map(x => x.id === action.alertId ? { ...x, acknowledged: true } : x) };
    case 'CLEAR_ALERTS': return { ...state, alerts: [] };
    case 'ADD_RULE': return { ...state, alertRules: [...state.alertRules, action.rule] };
    case 'UPDATE_RULE': return { ...state, alertRules: state.alertRules.map(x => x.id === action.ruleId ? { ...x, ...action.updates } : x) };
    case 'REMOVE_RULE': return { ...state, alertRules: state.alertRules.filter(x => x.id !== action.ruleId) };
    case 'ADD_RECORDING': return { ...state, recordings: [...state.recordings, action.recording] };
    case 'STOP_RECORDING': return { ...state, recordings: state.recordings.map(x => x.id === action.recordingId ? { ...x, endTime: Date.now() } : x) };
    case 'ADD_CREDENTIAL': return { ...state, credentials: [...state.credentials, action.credential] };
    case 'REMOVE_CREDENTIAL': return { ...state, credentials: state.credentials.filter(x => x.id !== action.credentialId) };
    case 'TOGGLE_MANUFACTURER': return { ...state, manufacturers: state.manufacturers.map(x => x.key === action.key ? { ...x, enabled: !x.enabled } : x) };
    default: return state;
  }
}

/* ─── Context ─── */

interface CtxValue {
  state: AppState;
  dispatch: React.Dispatch<Action>;
  togglePower: (id: string) => void;
  updateDevice: (id: string, u: Partial<Device>) => void;
  addDevice: (d: Device) => void;
  removeDevice: (id: string) => void;
  setSearch: (q: string) => void;
  setScanActive: (a: boolean) => void;
  setDiscovered: (d: DiscoveredDevice[]) => void;
  addDiscovered: (d: DiscoveredDevice) => void;
  updateDiscoveredPhase: (id: string, p: ScanPhase) => void;
  addZone: (z: Zone) => void;
  removeZone: (id: string) => void;
  updateZone: (id: string, u: Partial<Zone>) => void;
  addAlert: (a: CameraAlert) => void;
  ackAlert: (id: string) => void;
  clearAlerts: () => void;
  addRule: (r: AlertRule) => void;
  updateRule: (id: string, u: Partial<AlertRule>) => void;
  removeRule: (id: string) => void;
  addRecording: (r: CameraRecording) => void;
  stopRecording: (id: string) => void;
  addCredential: (c: Credential) => void;
  removeCredential: (id: string) => void;
  toggleManufacturer: (key: string) => void;
  cameras: Device[];
  unackAlerts: CameraAlert[];
  backendSync: BackendState;
}

const Ctx = createContext<CtxValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const backendSync = useBackendSync(dispatch);

  const togglePower = useCallback(async (id: string) => {
    const d = state.devices.find(x => x.id === id);
    if (!d) return;
    const newPower = !d.power;
    dispatch({ type: 'TOGGLE_DEVICE_POWER', deviceId: id });
    try {
      await api.sendCommand(id, { power: newPower });
    } catch (err) {
      // WebSocket will reconcile state
    }
  }, [state.devices]);
  const updateDevice = useCallback(async (id: string, u: Partial<Device>) => {
    dispatch({ type: 'UPDATE_DEVICE', deviceId: id, updates: u });
    const payload: Record<string, unknown> = {};
    if (u.brightness !== undefined) payload.brightness = u.brightness;
    if (u.color !== undefined) payload.color = u.color;
    if (u.targetTemp !== undefined) payload.target_temp = u.targetTemp;
    if (u.mode !== undefined) payload.mode = u.mode;
    if (u.power !== undefined) payload.power = u.power;
    if (Object.keys(payload).length === 0) return;
    try {
      await api.sendCommand(id, payload);
    } catch (err) {
      // WebSocket will reconcile state
    }
  }, []);
  const addDevice = useCallback((d: Device) => dispatch({ type: 'ADD_DEVICE', device: d }), []);
  const removeDevice = useCallback((id: string) => dispatch({ type: 'REMOVE_DEVICE', deviceId: id }), []);
  const setSearch = useCallback((q: string) => dispatch({ type: 'SET_SEARCH', query: q }), []);
  const setScanActive = useCallback((a: boolean) => dispatch({ type: 'SET_SCAN_ACTIVE', active: a }), []);
  const setDiscovered = useCallback((d: DiscoveredDevice[]) => dispatch({ type: 'SET_DISCOVERED', devices: d }), []);
  const addDiscovered = useCallback((d: DiscoveredDevice) => dispatch({ type: 'ADD_DISCOVERED', device: d }), []);
  const updateDiscoveredPhase = useCallback((id: string, p: ScanPhase) => dispatch({ type: 'UPDATE_DISCOVERED', id, phase: p }), []);
  const addZone = useCallback((z: Zone) => dispatch({ type: 'ADD_ZONE', zone: z }), []);
  const removeZone = useCallback((id: string) => dispatch({ type: 'REMOVE_ZONE', zoneId: id }), []);
  const updateZone = useCallback((id: string, u: Partial<Zone>) => dispatch({ type: 'UPDATE_ZONE', zoneId: id, updates: u }), []);
  const addAlert = useCallback((a: CameraAlert) => dispatch({ type: 'ADD_ALERT', alert: a }), []);
  const ackAlert = useCallback((id: string) => dispatch({ type: 'ACK_ALERT', alertId: id }), []);
  const clearAlerts = useCallback(() => dispatch({ type: 'CLEAR_ALERTS' }), []);
  const addRule = useCallback((r: AlertRule) => dispatch({ type: 'ADD_RULE', rule: r }), []);
  const updateRule = useCallback((id: string, u: Partial<AlertRule>) => dispatch({ type: 'UPDATE_RULE', ruleId: id, updates: u }), []);
  const removeRule = useCallback((id: string) => dispatch({ type: 'REMOVE_RULE', ruleId: id }), []);
  const addRecording = useCallback((r: CameraRecording) => dispatch({ type: 'ADD_RECORDING', recording: r }), []);
  const stopRecording = useCallback((id: string) => dispatch({ type: 'STOP_RECORDING', recordingId: id }), []);
  const addCredential = useCallback((c: Credential) => dispatch({ type: 'ADD_CREDENTIAL', credential: c }), []);
  const removeCredential = useCallback((id: string) => dispatch({ type: 'REMOVE_CREDENTIAL', credentialId: id }), []);
  const toggleManufacturer = useCallback((key: string) => dispatch({ type: 'TOGGLE_MANUFACTURER', key }), []);

  const cameras = React.useMemo(() => state.devices.filter(d => d.type === 'camera'), [state.devices]);
  const unackAlerts = React.useMemo(() => state.alerts.filter(a => !a.acknowledged), [state.alerts]);

  const value = React.useMemo<CtxValue>(() => ({
    state, dispatch, togglePower, updateDevice, addDevice, removeDevice,
    setSearch, setScanActive, setDiscovered, addDiscovered, updateDiscoveredPhase,
    addZone, removeZone, updateZone, addAlert, ackAlert, clearAlerts,
    addRule, updateRule, removeRule, addRecording, stopRecording,
    addCredential, removeCredential, toggleManufacturer, cameras, unackAlerts,
    backendSync,
  }), [state, togglePower, updateDevice, addDevice, removeDevice, setSearch, setScanActive, setDiscovered, addDiscovered, updateDiscoveredPhase, addZone, removeZone, updateZone, addAlert, ackAlert, clearAlerts, addRule, updateRule, removeRule, addRecording, stopRecording, addCredential, removeCredential, toggleManufacturer, cameras, unackAlerts, backendSync]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): CtxValue {
  const c = useContext(Ctx);
  if (!c) throw new Error('useApp must be used in AppProvider');
  return c;
}

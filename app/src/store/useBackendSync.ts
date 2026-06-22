import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '@/api/client';
import { wsClient } from '@/api/websocket';
import type { WsStatus } from '@/api/websocket';
import { mapDeviceState, mapDeviceStates, mapWsStateChange, mapDiscoveredDevice } from '@/api/mappers';
import type { Action } from './AppContext';
import type { DiscoveredDevice, ScanPhase } from '@/types';

/**
 * useBackendSync — Hybrid sync layer
 *
 * On mount: probes backend health, fetches devices/cameras if available
 * WebSocket: subscribes to real-time state + discovery scan events
 * Fallback: if backend is down, everything works with local seed state
 */

export interface BackendState {
  connected: boolean;
  wsStatus: WsStatus;
  deviceCount: number;
  cameraCount: number;
  syncing: boolean;
  error: string | null;
}

export function useBackendSync(dispatch: React.Dispatch<Action>) {
  const [state, setState] = useState<BackendState>({
    connected: false,
    wsStatus: 'disconnected',
    deviceCount: 0,
    cameraCount: 0,
    syncing: false,
    error: null,
  });

  const hasAttempted = useRef(false);

  const hydrateFromBackend = useCallback(async () => {
    setState(s => ({ ...s, syncing: true }));
    const res = await api.health();
    if (!res.ok || !res.data) {
      setState(s => ({
        ...s,
        connected: false,
        syncing: false,
        error: res.error || 'Backend unavailable',
      }));
      return false;
    }

    const listRes = await api.listDevices();
    if (listRes.ok && listRes.data) {
      dispatch({ type: 'SYNC_DEVICES', devices: mapDeviceStates(listRes.data as any[]) });
    }

    const camRes = await api.listCameras();
    const cameraCount = camRes.ok && Array.isArray(camRes.data) ? camRes.data.length : 0;

    setState(s => ({
      ...s,
      connected: true,
      deviceCount: res.data?.devices_registered || 0,
      cameraCount,
      syncing: false,
      error: null,
    }));

    wsClient.connect();
    return true;
  }, [dispatch]);

  useEffect(() => {
    if (hasAttempted.current) return;
    hasAttempted.current = true;

    let mounted = true;
    let unsubMessage: (() => void) | undefined;

    async function probe() {
      const ok = await hydrateFromBackend();
      if (!mounted || !ok) return;

      unsubMessage = wsClient.onMessage((msg) => {
        if (msg.type === 'state_change') {
          const device = mapWsStateChange(msg);
          if (!device) return;
          dispatch({
            type: 'UPDATE_DEVICE_FROM_BACKEND',
            deviceId: device.id,
            updates: device,
          });
          return;
        }

        if (msg.type === 'device_discovered' && msg.device) {
          const mapped = mapDiscoveredDevice(msg.device as any);
          dispatch({
            type: 'ADD_DISCOVERED',
            device: mapped as DiscoveredDevice,
          });
          return;
        }

        if (msg.type === 'scan_progress' || msg.type === 'scan_complete') {
          dispatch({ type: 'SET_SCAN_ACTIVE', active: Boolean(msg.active) });
          if (typeof msg.message === 'string') {
            dispatch({
              type: 'SET_DISCOVERY_SCAN',
              progress: Number(msg.progress) || 0,
              message: msg.message,
            });
          }
          if (msg.type === 'scan_complete') {
            api.listDiscovered().then((r) => {
              if (r.ok && r.data) {
                dispatch({
                  type: 'SET_DISCOVERED',
                  devices: r.data.map((d: any) => mapDiscoveredDevice(d) as DiscoveredDevice),
                });
              }
            });
          }
        }
      });
    }

    probe();

    const unsub = wsClient.onStatusChange((wsStatus) => {
      if (!mounted) return;
      setState(s => ({
        ...s,
        wsStatus,
        connected: wsStatus === 'connected' || s.connected,
      }));
    });

    return () => {
      mounted = false;
      unsub();
      unsubMessage?.();
    };
  }, [dispatch, hydrateFromBackend]);

  const refresh = useCallback(async () => {
    await hydrateFromBackend();
    const listRes = await api.listDevices();
    if (listRes.ok && listRes.data) {
      dispatch({ type: 'SYNC_DEVICES', devices: mapDeviceStates(listRes.data as any[]) });
    }
  }, [dispatch, hydrateFromBackend]);

  const reconnectWs = useCallback(() => {
    wsClient.connect();
  }, []);

  return { ...state, refresh, reconnectWs };
}
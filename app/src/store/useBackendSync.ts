import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '@/api/client';
import { wsClient } from '@/api/websocket';
import type { WsStatus } from '@/api/websocket';
import { mapDeviceState, mapDeviceStates } from '@/api/mappers';
import type { Action } from './AppContext';

/**
 * useBackendSync — Hybrid sync layer
 * 
 * On mount: probes backend health, fetches devices if available
 * WebSocket: subscribes to real-time state changes
 * Fallback: if backend is down, everything works with local state
 */

export interface BackendState {
  connected: boolean;
  wsStatus: WsStatus;
  deviceCount: number;
  syncing: boolean;
  error: string | null;
}

export function useBackendSync(dispatch: React.Dispatch<Action>) {
  const [state, setState] = useState<BackendState>({
    connected: false,
    wsStatus: 'disconnected',
    deviceCount: 0,
    syncing: false,
    error: null,
  });

  const hasAttempted = useRef(false);

  // Probe backend on mount
  useEffect(() => {
    if (hasAttempted.current) return;
    hasAttempted.current = true;

    let mounted = true;
    let unsubMessage: (() => void) | undefined;

    async function probe() {
      setState(s => ({ ...s, syncing: true }));
      const res = await api.health();
      if (!mounted) return;

      if (res.ok && res.data) {
        setState(s => ({
          ...s,
          connected: true,
          deviceCount: res.data?.devices_registered || 0,
          syncing: false,
          error: null,
        }));
        // Connect WebSocket for real-time updates
        wsClient.connect();

        // Fetch full device list
        const listRes = await api.listDevices();
        if (mounted && listRes.ok && listRes.data) {
          dispatch({ type: 'SYNC_DEVICES', devices: mapDeviceStates(listRes.data as any[]) });
        }

        // Subscribe to real-time state changes
        unsubMessage = wsClient.onMessage((msg) => {
          if (msg.type === 'state_change' && msg.state) {
            const device = mapDeviceState(msg.state as any);
            dispatch({
              type: 'UPDATE_DEVICE_FROM_BACKEND',
              deviceId: device.id,
              updates: device,
            });
          }
        });
      } else {
        setState(s => ({
          ...s,
          connected: false,
          syncing: false,
          error: res.error || 'Backend unavailable',
        }));
      }
    }

    probe();

    // Subscribe to WebSocket status
    const unsub = wsClient.onStatusChange((wsStatus) => {
      if (!mounted) return;
      setState(s => ({
        ...s,
        wsStatus,
        connected: wsStatus === 'connected',
      }));
    });

    return () => {
      mounted = false;
      unsub();
      unsubMessage?.();
    };
  }, [dispatch]);

  const refresh = useCallback(async () => {
    setState(s => ({ ...s, syncing: true }));
    const res = await api.health();
    if (res.ok) {
      setState(s => ({
        ...s,
        connected: true,
        deviceCount: res.data?.devices_registered || 0,
        syncing: false,
        error: null,
      }));
      wsClient.connect();
      const listRes = await api.listDevices();
      if (listRes.ok && listRes.data) {
        dispatch({ type: 'SYNC_DEVICES', devices: mapDeviceStates(listRes.data as any[]) });
      }
    } else {
      setState(s => ({
        ...s,
        connected: false,
        syncing: false,
        error: res.error || 'Backend unavailable',
      }));
    }
  }, [dispatch]);

  const reconnectWs = useCallback(() => {
    wsClient.connect();
  }, []);

  return { ...state, refresh, reconnectWs };
}

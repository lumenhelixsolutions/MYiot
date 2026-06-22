import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Scan, Plus, Check, X, Loader2, Wifi, Lightbulb, Power,
  Thermometer, Video, Server, Radar, Globe,
} from 'lucide-react';
import { useApp } from '@/store/AppContext';
import { api } from '@/api/client';
import { mapDiscoveredDevice } from '@/api/mappers';
import type { DeviceType, ScanPhase, DiscoveredDevice, Device } from '@/types';

const typeIcon = (t: DeviceType) => {
  if (t === 'light') return Lightbulb;
  if (t === 'plug') return Power;
  if (t === 'thermostat') return Thermometer;
  return Video;
};
const typeColor = (t: DeviceType) => {
  if (t === 'light') return '#fbbf24';
  if (t === 'plug') return '#10b981';
  if (t === 'thermostat') return '#f97316';
  return '#ef4444';
};
const phaseConfig: Record<ScanPhase, { color: string; label: string }> = {
  idle: { color: '#475569', label: 'Idle' },
  probing: { color: '#06b6d4', label: 'Probing...' },
  authenticating: { color: '#f59e0b', label: 'Authenticating' },
  classifying: { color: '#8b5cf6', label: 'Classifying' },
  complete: { color: '#10b981', label: 'Ready' },
};

const mfrList = [
  'Philips Hue', 'TP-Link Kasa', 'Nest', 'Wemo', 'LIFX', 'Govee', 'Wyze',
  'IKEA Tradfri', 'Ecobee', 'Ring', 'EOOEIES', 'Sonoff', 'Meross',
  'Lutron Caseta', 'Blink', 'Honeywell', 'Emerson Sensi',
];

function genId(p: string) {
  return `${p}-${Date.now()}-${Math.random().toString(36).substring(2, 5)}`;
}

export default function Discovery() {
  const {
    state, addDevice, setScanActive, setDiscovered, backendSync,
  } = useApp();

  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(state.discoveryProgress);
  const [scanMsg, setScanMsg] = useState(state.discoveryMessage);
  const [discovered, setDiscoveredLocal] = useState<DiscoveredDevice[]>(state.discoveredDevices);
  const [pairingDev, setPairingDev] = useState<DiscoveredDevice | null>(null);
  const [pairStep, setPairStep] = useState(0);
  const [showManual, setShowManual] = useState(false);
  const [mName, setMName] = useState('');
  const [mIp, setMIp] = useState('');
  const [mMfr, setMMfr] = useState(mfrList[0]);
  const [mType, setMType] = useState<DeviceType>('light');
  const [mProtocol, setMProtocol] = useState('REST');
  const [mPort, setMPort] = useState('80');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setProgress(state.discoveryProgress);
    setScanMsg(state.discoveryMessage);
    setScanning(state.scanActive);
    if (state.discoveredDevices.length > 0) {
      setDiscoveredLocal(state.discoveredDevices);
    }
  }, [state.discoveryProgress, state.discoveryMessage, state.scanActive, state.discoveredDevices]);

  const clearPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => clearPoll(), [clearPoll]);

  const pollScanStatus = useCallback(() => {
    clearPoll();
    pollRef.current = setInterval(async () => {
      const status = await api.discoveryStatus();
      if (!status.ok || !status.data) return;
      setProgress(status.data.progress);
      setScanMsg(status.data.message);
      setScanning(status.data.active);
      if (!status.data.active && status.data.progress >= 100) {
        clearPoll();
        const list = await api.listDiscovered();
        if (list.ok && list.data) {
          const mapped = list.data.map((d: any) => mapDiscoveredDevice(d) as DiscoveredDevice);
          setDiscoveredLocal(mapped);
          setDiscovered(mapped);
        }
      }
    }, 800);
  }, [clearPoll, setDiscovered]);

  const startScan = useCallback(async () => {
    setScanning(true);
    setProgress(0);
    setScanMsg('Initializing global scan...');
    setDiscoveredLocal([]);
    setDiscovered([]);
    setScanActive(true);

    if (backendSync.connected) {
      const res = await api.startDiscoveryScan();
      if (res.ok) {
        pollScanStatus();
        return;
      }
      setScanMsg(res.error || 'Scan failed to start');
      setScanning(false);
      setScanActive(false);
      return;
    }

    setScanMsg('Backend offline — enable the hub for live network discovery');
    setScanning(false);
    setScanActive(false);
    setProgress(0);
  }, [backendSync.connected, pollScanStatus, setDiscovered, setScanActive]);

  const stopScan = useCallback(async () => {
    clearPoll();
    if (backendSync.connected) {
      await api.stopDiscoveryScan();
    }
    setScanning(false);
    setProgress(0);
    setScanMsg('');
    setScanActive(false);
  }, [backendSync.connected, clearPoll, setScanActive]);

  const startPairing = async (dev: DiscoveredDevice) => {
    setPairingDev(dev);
    setPairStep(0);

    if (backendSync.connected) {
      setPairStep(1);
      const res = await api.registerDiscovered(dev.id, { name: dev.name });
      setPairStep(res.ok ? 3 : 2);
      if (res.ok) {
        await backendSync.refresh();
        setDiscoveredLocal(prev => prev.filter(d => d.id !== dev.id));
      }
      return;
    }

    setTimeout(() => setPairStep(1), 1200);
    setTimeout(() => setPairStep(2), 2400);
    setTimeout(() => {
      setPairStep(3);
      const newDev: Device = {
        id: genId('dev'),
        name: dev.name,
        manufacturer: dev.manufacturer,
        model: 'Unknown',
        type: dev.type,
        room: 'Unassigned',
        online: true,
        power: false,
        ipAddress: dev.ipAddress,
        protocol: dev.protocol,
        signalStrength: dev.signalStrength,
        lastSeen: Date.now(),
        firmware: dev.firmware || 'Unknown',
        streamUrl: dev.type === 'camera' ? `rtsp://${dev.ipAddress}:554/live` : undefined,
      };
      addDevice(newDev);
    }, 3600);
  };

  const handleManualAdd = async () => {
    if (!mName.trim() || !mIp.trim()) return;
    const deviceId = genId('dev');

    if (backendSync.connected) {
      const res = await api.addManual({
        device_id: deviceId,
        manufacturer: mMfr,
        device_type: mType,
        ip_address: mIp.trim(),
        port: Number(mPort) || 80,
        protocol: mProtocol,
        name: mName.trim(),
        room: 'Unassigned',
      });
      if (res.ok) {
        await backendSync.refresh();
        setMName('');
        setMIp('');
        setShowManual(false);
      }
      return;
    }

    const newDev: Device = {
      id: deviceId,
      name: mName.trim(),
      manufacturer: mMfr,
      model: 'Custom',
      type: mType,
      room: 'Unassigned',
      online: true,
      power: false,
      ipAddress: mIp.trim(),
      protocol: mProtocol,
      signalStrength: 100,
      lastSeen: Date.now(),
      firmware: 'Unknown',
      streamUrl: mType === 'camera' ? `rtsp://${mIp.trim()}:${mPort}/live` : undefined,
    };
    addDevice(newDev);
    setMName('');
    setMIp('');
    setShowManual(false);
  };

  return (
    <div className="flex flex-col gap-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="hero-panel relative overflow-hidden rounded-3xl py-10"
      >
        <div className="pointer-events-none absolute inset-0 opacity-40" style={{
          background: 'radial-gradient(ellipse 80% 60% at 50% 0%, rgba(139,92,246,0.35), transparent 70%)',
        }} />

        <div className="relative flex flex-col items-center gap-6 px-6">
          <div className="flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-medium" style={{
            backgroundColor: 'rgba(99,102,241,0.12)',
            color: 'var(--accent-primary-light)',
            border: '1px solid rgba(99,102,241,0.2)',
          }}>
            <Globe className="h-3.5 w-3.5" />
            Global IoT Scanner — SSDP · mDNS · UDP
          </div>

          <div className="relative flex h-40 w-40 items-center justify-center">
            {[0, 1, 2].map(ring => (
              <div
                key={ring}
                className="absolute rounded-full"
                style={{
                  inset: `${ring * 18}px`,
                  border: `1px solid rgba(139,92,246,${0.14 - ring * 0.03})`,
                }}
              />
            ))}
            {scanning && (
              <motion.div
                className="absolute inset-0 rounded-full"
                style={{ background: 'conic-gradient(from 0deg, transparent 65%, rgba(139,92,246,0.2) 100%)' }}
                animate={{ rotate: 360 }}
                transition={{ duration: 2.2, repeat: Infinity, ease: 'linear' }}
              />
            )}
            {discovered.map((d, i) => (
              <motion.div
                key={d.id}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="absolute h-2 w-2 rounded-full"
                style={{
                  backgroundColor: typeColor(d.type),
                  boxShadow: `0 0 8px ${typeColor(d.type)}`,
                  top: `${22 + (i * 17) % 56}%`,
                  left: `${24 + (i * 23) % 52}%`,
                }}
              />
            ))}
            <Radar className="h-9 w-9" style={{ color: scanning ? 'var(--accent-tertiary)' : 'var(--text-muted)' }} />
          </div>

          {scanning && (
            <div className="w-72">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{scanMsg}</span>
                <span className="text-xs font-semibold tabular-nums" style={{ color: 'var(--text-primary)' }}>{progress}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full" style={{ backgroundColor: 'var(--bg-inset)' }}>
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: 'linear-gradient(90deg, #6366F1, #8B5CF6, #06B6D4)' }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.25 }}
                />
              </div>
            </div>
          )}

          {!scanning && progress === 100 && scanMsg && (
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4" style={{ color: '#10b981' }} />
              <span className="text-sm font-medium" style={{ color: '#10b981' }}>{scanMsg}</span>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              onClick={scanning ? stopScan : startScan}
              disabled={!backendSync.connected && !scanning}
              className="flex items-center gap-2 rounded-xl px-7 py-3 text-sm font-semibold text-white transition-all hover:scale-[1.02] disabled:opacity-50"
              style={{ background: scanning ? '#ef4444' : 'linear-gradient(135deg, #6366F1, #8B5CF6)' }}
            >
              {scanning ? <><X className="h-4 w-4" /> Stop Scan</> : <><Scan className="h-4 w-4" /> Start Global Scan</>}
            </button>
            <button
              onClick={() => setShowManual(!showManual)}
              className="flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-medium transition-all"
              style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}
            >
              <Plus className="h-4 w-4" /> Manual Add
            </button>
          </div>

          <div className="flex flex-wrap justify-center gap-2">
            {['mDNS', 'SSDP', 'UPnP', 'UDP Broadcast', 'HomeKit', 'CoAP'].map(p => (
              <span key={p} className="rounded-full px-3 py-1 text-[10px] font-medium" style={{
                backgroundColor: 'rgba(255,255,255,0.03)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border-subtle)',
              }}>{p}</span>
            ))}
          </div>

          {!backendSync.connected && (
            <p className="text-center text-xs" style={{ color: 'var(--status-warn)' }}>
              Start the MYiot hub (port 8000) for live network discovery and WebSocket sync.
            </p>
          )}
        </div>
      </motion.div>

      {discovered.length > 0 && (
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
            Discovered ({discovered.length})
          </h3>
          <div className="grid gap-2">
            {discovered.map((dev, i) => {
              const Icon = typeIcon(dev.type);
              const color = typeColor(dev.type);
              const phase = phaseConfig[dev.scanPhase];
              return (
                <motion.div
                  key={dev.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="glass-card flex items-center justify-between rounded-2xl p-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ backgroundColor: `${color}18` }}>
                      <Icon className="h-5 w-5" style={{ color }} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{dev.name}</p>
                      <p className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>
                        {dev.ipAddress} · {dev.manufacturer} · {dev.protocol}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5">
                      <div className="h-2 w-2 rounded-full" style={{ backgroundColor: phase.color }} />
                      {dev.scanPhase !== 'complete'
                        ? <Loader2 className="h-3 w-3 animate-spin" style={{ color: phase.color }} />
                        : <Check className="h-3 w-3" style={{ color: phase.color }} />}
                      <span className="text-[11px]" style={{ color: phase.color }}>{phase.label}</span>
                    </div>
                    {dev.scanPhase === 'complete' ? (
                      <button
                        onClick={() => startPairing(dev)}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold text-white"
                        style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}
                      >
                        <Plus className="mr-1 inline h-3 w-3" />Add to Hub
                      </button>
                    ) : (
                      <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Analyzing...</span>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      <AnimatePresence>
        {pairingDev && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center"
            style={{ backgroundColor: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(10px)' }}
            onClick={() => { if (pairStep >= 3) { setPairingDev(null); setPairStep(0); } }}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex w-full max-w-sm flex-col items-center rounded-2xl p-8"
              style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}
              onClick={e => e.stopPropagation()}
            >
              {pairStep < 3 ? (
                <>
                  <Loader2 className="h-10 w-10 animate-spin" style={{ color: 'var(--accent-tertiary)' }} />
                  <p className="mt-4 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {pairStep === 0 ? 'Registering on hub...' : pairStep === 1 ? 'Syncing drivers...' : 'Retry or check logs...'}
                  </p>
                  <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>{pairingDev.name}</p>
                </>
              ) : (
                <>
                  <div className="flex h-14 w-14 items-center justify-center rounded-full" style={{ backgroundColor: 'rgba(16,185,129,0.15)' }}>
                    <Check className="h-7 w-7" style={{ color: '#10b981' }} />
                  </div>
                  <p className="mt-4 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>{pairingDev.name} is live</p>
                  <button
                    onClick={() => { setPairingDev(null); setPairStep(0); }}
                    className="mt-5 rounded-xl px-6 py-2.5 text-sm font-medium text-white"
                    style={{ backgroundColor: 'var(--accent-primary)' }}
                  >Done</button>
                </>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showManual && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="glass-card overflow-hidden rounded-2xl p-5"
          >
            <h3 className="mb-4 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Add Device Manually</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>Name *</label>
                <input value={mName} onChange={e => setMName(e.target.value)} className="input-field w-full" placeholder="Living Room Light" />
              </div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>IP *</label>
                <input value={mIp} onChange={e => setMIp(e.target.value)} className="input-field w-full font-mono" placeholder="192.168.1.100" />
              </div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>Manufacturer</label>
                <select value={mMfr} onChange={e => setMMfr(e.target.value)} className="input-field w-full">
                  {mfrList.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>Type</label>
                <select value={mType} onChange={e => setMType(e.target.value as DeviceType)} className="input-field w-full">
                  <option value="light">Light</option>
                  <option value="plug">Plug</option>
                  <option value="thermostat">Thermostat</option>
                  <option value="camera">Camera</option>
                </select>
              </div>
            </div>
            <button
              onClick={handleManualAdd}
              disabled={!mName.trim() || !mIp.trim()}
              className="mt-4 rounded-xl px-6 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: 'linear-gradient(135deg, #6366F1, #8B5CF6)' }}
            >Add Device</button>
          </motion.div>
        )}
      </AnimatePresence>

      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Network Map</h3>
        <div className="glass-card relative min-h-[220px] rounded-2xl p-6">
          <div className="mb-6 flex flex-col items-center gap-1">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl" style={{
              background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.15))',
              border: '2px solid var(--accent-primary)',
            }}>
              <Server className="h-7 w-7" style={{ color: 'var(--accent-primary)' }} />
            </div>
            <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>MYiot Hub</span>
            <span className="text-[10px]" style={{ color: backendSync.connected ? '#10b981' : 'var(--text-muted)' }}>
              {backendSync.connected ? 'Connected · WebSocket live' : 'Offline mode'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
            {state.devices.map(d => {
              const Icon = typeIcon(d.type);
              return (
                <div key={d.id} className="flex items-center gap-2 rounded-xl px-3 py-2" style={{ backgroundColor: 'var(--bg-inset)' }}>
                  <div className={`h-2 w-2 rounded-full ${d.online ? 'bg-emerald-500' : 'bg-gray-600'}`} />
                  <Icon className="h-3.5 w-3.5" style={{ color: typeColor(d.type) }} />
                  <span className="truncate text-[11px] font-medium" style={{ color: 'var(--text-secondary)' }}>{d.name}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
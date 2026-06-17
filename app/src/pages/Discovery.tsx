import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Scan, Plus, Check, X, Loader2, Wifi, Lightbulb, Power,
  Thermometer, Video, Server,
} from 'lucide-react';
import { useApp } from '@/store/AppContext';
import type { DeviceType, ScanPhase, DiscoveredDevice, Device } from '@/types';

const typeIcon = (t: DeviceType) => { if (t === 'light') return Lightbulb; if (t === 'plug') return Power; if (t === 'thermostat') return Thermometer; return Video; };
const typeColor = (t: DeviceType) => { if (t === 'light') return '#fbbf24'; if (t === 'plug') return '#10b981'; if (t === 'thermostat') return '#f97316'; return '#ef4444'; };
const phaseConfig: Record<ScanPhase, { color: string; label: string }> = {
  idle: { color: '#475569', label: 'Idle' },
  probing: { color: '#06b6d4', label: 'Probing...' },
  authenticating: { color: '#f59e0b', label: 'Authenticating' },
  classifying: { color: '#8b5cf6', label: 'Classifying' },
  complete: { color: '#10b981', label: 'Ready' },
};

const candidates: Array<{ name: string; manufacturer: string; type: DeviceType; protocol: string; ip: string; mac: string }> = [
  { name: 'Front Porch Cam', manufacturer: 'Ring', type: 'camera', protocol: 'REST', ip: '192.168.1.130', mac: 'AA:BB:CC:11:22:30' },
  { name: 'Smart Bulb A19', manufacturer: 'Philips Hue', type: 'light', protocol: 'REST', ip: '192.168.1.131', mac: 'AA:BB:CC:11:22:31' },
  { name: 'Kitchen Outlet', manufacturer: 'TP-Link Kasa', type: 'plug', protocol: 'TCP', ip: '192.168.1.132', mac: 'AA:BB:CC:11:22:32' },
  { name: 'Bedroom Cam', manufacturer: 'Wyze', type: 'camera', protocol: 'REST', ip: '192.168.1.133', mac: 'AA:BB:CC:11:22:33' },
  { name: 'Desk Lamp', manufacturer: 'IKEA Tradfri', type: 'light', protocol: 'CoAP', ip: '192.168.1.134', mac: 'AA:BB:CC:11:22:34' },
  { name: 'Thermostat', manufacturer: 'Ecobee', type: 'thermostat', protocol: 'REST', ip: '192.168.1.135', mac: 'AA:BB:CC:11:22:35' },
  { name: 'Outdoor Cam', manufacturer: 'EOOEIES', type: 'camera', protocol: 'REST', ip: '192.168.1.136', mac: 'AA:BB:CC:11:22:36' },
  { name: 'Garden Plug', manufacturer: 'Sonoff', type: 'plug', protocol: 'REST', ip: '192.168.1.137', mac: 'AA:BB:CC:11:22:37' },
];

const mfrList = ['Philips Hue', 'TP-Link Kasa', 'Nest', 'Wemo', 'LIFX', 'Govee', 'Wyze', 'IKEA Tradfri', 'Ecobee', 'Ring', 'EOOEIES', 'Sonoff', 'Meross', 'Lutron Caseta', 'Blink', 'Honeywell', 'Emerson Sensi'];

function genId(p: string) { return `${p}-${Date.now()}-${Math.random().toString(36).substring(2, 5)}`; }

export default function Discovery() {
  const { state, addDevice, setScanActive } = useApp();
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [scanMsg, setScanMsg] = useState('');
  const [discovered, setDiscovered] = useState<DiscoveredDevice[]>([]);
  const [pairingDev, setPairingDev] = useState<DiscoveredDevice | null>(null);
  const [pairStep, setPairStep] = useState(0);
  const [showManual, setShowManual] = useState(false);
  const [mName, setMName] = useState('');
  const [mIp, setMIp] = useState('');
  const [mMfr, setMMfr] = useState(mfrList[0]);
  const [mType, setMType] = useState<DeviceType>('light');
  const [mProtocol, setMProtocol] = useState('REST');
  const [mPort, setMPort] = useState('80');
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = useCallback(() => { timersRef.current.forEach(t => clearTimeout(t)); timersRef.current = []; }, []);

  useEffect(() => () => clearTimers(), [clearTimers]);

  const startScan = useCallback(() => {
    clearTimers();
    setScanning(true); setProgress(0); setScanMsg('Initializing...'); setDiscovered([]); setScanActive(true);
    const shuffled = [...candidates].sort(() => Math.random() - 0.5);
    const pickCount = 5 + Math.floor(Math.random() * 4);
    const picked = shuffled.slice(0, pickCount);

    picked.forEach((cand, idx) => {
      const t = setTimeout(() => {
        const dev: DiscoveredDevice = { id: genId('disc'), name: cand.name, manufacturer: cand.manufacturer, type: cand.type, ipAddress: cand.ip, protocol: cand.protocol, signalStrength: Math.floor(55 + Math.random() * 40), scanPhase: 'probing', macAddress: cand.mac, firmware: `1.${Math.floor(Math.random() * 9)}.${Math.floor(Math.random() * 99)}` };
        setDiscovered(prev => [...prev, dev]);
      }, 800 + idx * 900 + Math.random() * 400);
      timersRef.current.push(t);
    });

    const phaseTimer = setInterval(() => {
      setDiscovered(prev => prev.map(d => {
        if (d.scanPhase === 'probing') return { ...d, scanPhase: 'authenticating' as ScanPhase };
        if (d.scanPhase === 'authenticating') return { ...d, scanPhase: 'classifying' as ScanPhase };
        if (d.scanPhase === 'classifying') return { ...d, scanPhase: 'complete' as ScanPhase };
        return d;
      }));
    }, 1500);
    timersRef.current.push(phaseTimer as unknown as ReturnType<typeof setTimeout>);

    const msgs = ['Probing mDNS...', 'Scanning SSDP...', 'Checking UDP...', 'Querying devices...', 'Classifying...', 'Finalizing...'];
    let prog = 0;
    const progTimer = setInterval(() => { prog += 2; setProgress(Math.min(prog, 100)); setScanMsg(msgs[Math.floor((prog / 100) * msgs.length)] || 'Complete'); }, 160);
    timersRef.current.push(progTimer as unknown as ReturnType<typeof setTimeout>);

    const doneTimer = setTimeout(() => { clearInterval(phaseTimer); clearInterval(progTimer); setScanning(false); setScanActive(false); setProgress(100); setScanMsg(`Found ${pickCount} devices`); }, 8000);
    timersRef.current.push(doneTimer);
  }, [clearTimers, setScanActive]);

  const stopScan = useCallback(() => { clearTimers(); setScanning(false); setProgress(0); setScanMsg(''); setScanActive(false); }, [clearTimers, setScanActive]);

  const startPairing = (dev: DiscoveredDevice) => {
    setPairingDev(dev); setPairStep(0);
    timersRef.current.push(setTimeout(() => setPairStep(1), 1500));
    timersRef.current.push(setTimeout(() => setPairStep(2), 3000));
    timersRef.current.push(setTimeout(() => {
      setPairStep(3);
      const newDev: Device = { id: genId('dev'), name: dev.name, manufacturer: dev.manufacturer, model: 'Unknown', type: dev.type, room: 'Unassigned', online: true, power: false, ipAddress: dev.ipAddress, protocol: dev.protocol, signalStrength: dev.signalStrength, lastSeen: Date.now(), firmware: dev.firmware || 'Unknown', streamUrl: dev.type === 'camera' ? `rtsp://${dev.ipAddress}:554/live` : undefined };
      addDevice(newDev);
    }, 5000));
  };

  const handleManualAdd = () => {
    if (!mName.trim() || !mIp.trim()) return;
    const newDev: Device = { id: genId('dev'), name: mName.trim(), manufacturer: mMfr, model: 'Custom', type: mType, room: 'Unassigned', online: true, power: false, ipAddress: mIp.trim(), protocol: mProtocol, signalStrength: 100, lastSeen: Date.now(), firmware: 'Unknown', streamUrl: mType === 'camera' ? `rtsp://${mIp.trim()}:${mPort}/live` : undefined };
    addDevice(newDev);
    setMName(''); setMIp(''); setShowManual(false);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Radar */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col items-center gap-5 rounded-2xl py-8" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
        <div className="relative flex h-36 w-36 items-center justify-center">
          <div className="absolute inset-0 rounded-full" style={{ border: '1px solid rgba(139,92,246,0.12)' }} />
          <div className="absolute inset-5 rounded-full" style={{ border: '1px solid rgba(139,92,246,0.08)' }} />
          <div className="absolute inset-10 rounded-full" style={{ border: '1px solid rgba(139,92,246,0.05)' }} />
          {scanning && <motion.div className="absolute inset-0 rounded-full" style={{ background: 'conic-gradient(from 0deg, transparent 70%, rgba(139,92,246,0.15) 100%)' }} animate={{ rotate: 360 }} transition={{ duration: 2, repeat: Infinity, ease: 'linear' }} />}
          {discovered.map(d => <motion.div key={d.id} initial={{ scale: 0 }} animate={{ scale: 1 }} className="absolute h-1.5 w-1.5 rounded-full" style={{ backgroundColor: typeColor(d.type), boxShadow: `0 0 6px ${typeColor(d.type)}`, top: `${20 + Math.random() * 60}%`, left: `${20 + Math.random() * 60}%` }} />)}
          <Scan className="h-7 w-7" style={{ color: scanning ? 'var(--accent-tertiary)' : 'var(--text-muted)' }} />
        </div>
        {scanning && (
          <div className="w-56">
            <div className="mb-1 flex items-center justify-between"><span className="text-xs" style={{ color: 'var(--text-muted)' }}>{scanMsg}</span><span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{progress}%</span></div>
            <div className="h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: 'var(--bg-inset)' }}>
              <motion.div className="h-full rounded-full" style={{ backgroundColor: 'var(--accent-tertiary)' }} animate={{ width: `${progress}%` }} transition={{ duration: 0.2 }} />
            </div>
          </div>
        )}
        {!scanning && progress === 100 && <div className="flex items-center gap-2"><Check className="h-4 w-4" style={{ color: '#10b981' }} /><span className="text-sm font-medium" style={{ color: '#10b981' }}>{scanMsg}</span></div>}
        <div className="flex items-center gap-3">
          <button onClick={scanning ? stopScan : startScan} className="flex items-center gap-2 rounded-xl px-6 py-2.5 text-sm font-medium text-white transition-all hover:opacity-90" style={{ backgroundColor: scanning ? '#ef4444' : 'var(--accent-tertiary)' }}>{scanning ? <><X className="h-4 w-4" /> Stop</> : <><Scan className="h-4 w-4" /> Start Scan</>}</button>
          <button onClick={() => setShowManual(!showManual)} className="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all" style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}><Plus className="h-4 w-4" /> Manual</button>
        </div>
        <div className="flex gap-2">{['mDNS', 'SSDP', 'UPnP', 'TCP Direct'].map(p => <span key={p} className="rounded-full px-2.5 py-0.5 text-[10px] font-medium" style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>{p}</span>)}</div>
      </motion.div>

      {/* Discovered */}
      {discovered.length > 0 && (
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Discovered ({discovered.length})</h3>
          <div className="flex flex-col gap-2">
            {discovered.map(dev => {
              const Icon = typeIcon(dev.type); const color = typeColor(dev.type); const phase = phaseConfig[dev.scanPhase];
              return (
                <motion.div key={dev.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between rounded-xl p-3" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg" style={{ backgroundColor: `${color}15` }}><Icon className="h-4 w-4" style={{ color }} /></div>
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{dev.name}</p>
                      <p className="text-[11px] font-mono" style={{ color: 'var(--text-muted)' }}>{dev.ipAddress} · {dev.macAddress} · {dev.protocol}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-full" style={{ backgroundColor: phase.color }} />{dev.scanPhase !== 'complete' ? <Loader2 className="h-3 w-3 animate-spin" style={{ color: phase.color }} /> : <Check className="h-3 w-3" style={{ color: phase.color }} />}<span className="text-[11px]" style={{ color: phase.color }}>{phase.label}</span></div>
                    {dev.scanPhase === 'complete' ? <button onClick={() => startPairing(dev)} className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-white" style={{ backgroundColor: '#10b981' }}><Plus className="h-3 w-3" /> Add</button>
                      : <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Waiting...</span>}
                    <button onClick={() => setDiscovered(prev => prev.filter(x => x.id !== dev.id))} className="rounded p-1 hover:bg-white/5"><X className="h-3.5 w-3.5" style={{ color: 'var(--text-muted)' }} /></button>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pairing Modal */}
      <AnimatePresence>
        {pairingDev && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[100] flex items-center justify-center" style={{ backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)' }} onClick={() => { if (pairStep >= 3) { setPairingDev(null); setPairStep(0); } }}>
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="flex w-full max-w-sm flex-col items-center rounded-2xl p-8" style={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }} onClick={e => e.stopPropagation()}>
              {pairStep < 3 ? (
                <><Loader2 className="h-10 w-10 animate-spin" style={{ color: 'var(--accent-tertiary)' }} /><p className="mt-4 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>{pairStep === 0 ? 'Adding to hub...' : pairStep === 1 ? 'Syncing config...' : 'Finalizing...'}</p><p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>{pairingDev.name}</p>
                  <div className="mt-4 flex w-full gap-2">{['Add', 'Sync', 'Ready'].map((l, i) => <div key={l} className="flex-1"><div className="h-1.5 rounded-full" style={{ backgroundColor: i <= pairStep ? 'var(--accent-tertiary)' : 'var(--bg-inset)' }} /><p className="mt-1 text-center text-[10px]" style={{ color: i <= pairStep ? 'var(--accent-tertiary)' : 'var(--text-muted)' }}>{l}</p></div>)}</div></>
              ) : (
                <><div className="flex h-14 w-14 items-center justify-center rounded-full" style={{ backgroundColor: 'rgba(16,185,129,0.15)' }}><Check className="h-7 w-7" style={{ color: '#10b981' }} /></div><p className="mt-4 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>{pairingDev.name} added!</p><p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>Ready to use</p><button onClick={() => { setPairingDev(null); setPairStep(0); window.location.hash = '/devices'; window.location.reload(); }} className="mt-5 rounded-xl px-6 py-2.5 text-sm font-medium text-white" style={{ backgroundColor: 'var(--accent-primary)' }}>Go to Devices</button></>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Manual Entry */}
      <AnimatePresence>
        {showManual && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden rounded-2xl p-5" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
            <h3 className="mb-4 text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Add Device Manually</h3>
            <div className="grid grid-cols-2 gap-4">
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>Name *</label><input value={mName} onChange={e => setMName(e.target.value)} className="w-full rounded-lg border px-3 py-2 text-sm outline-none" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }} placeholder="Living Room Light" /></div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>IP *</label><input value={mIp} onChange={e => setMIp(e.target.value)} className="w-full rounded-lg border px-3 py-2 text-sm font-mono outline-none" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }} placeholder="192.168.1.100" /></div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>Manufacturer</label><select value={mMfr} onChange={e => setMMfr(e.target.value)} className="w-full rounded-lg border px-3 py-2 text-sm outline-none" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}>{mfrList.map(m => <option key={m} value={m}>{m}</option>)}</select></div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>Type</label><select value={mType} onChange={e => setMType(e.target.value as DeviceType)} className="w-full rounded-lg border px-3 py-2 text-sm outline-none" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}><option value="light">Light</option><option value="plug">Plug</option><option value="thermostat">Thermostat</option><option value="camera">Camera</option></select></div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>Protocol</label><select value={mProtocol} onChange={e => setMProtocol(e.target.value)} className="w-full rounded-lg border px-3 py-2 text-sm outline-none" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }}><option>REST</option><option>TCP</option><option>CoAP</option><option>SOAP</option><option>MQTT</option></select></div>
              <div><label className="mb-1 block text-xs" style={{ color: 'var(--text-muted)' }}>Port</label><input value={mPort} onChange={e => setMPort(e.target.value)} className="w-full rounded-lg border px-3 py-2 text-sm font-mono outline-none" style={{ backgroundColor: 'var(--bg-inset)', borderColor: 'var(--border-subtle)', color: 'var(--text-primary)' }} /></div>
            </div>
            <button onClick={handleManualAdd} disabled={!mName.trim() || !mIp.trim()} className="mt-4 rounded-xl px-6 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40" style={{ backgroundColor: 'var(--accent-primary)' }}>Add Device</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Network Map */}
      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Network Map</h3>
        <div className="relative flex min-h-[200px] items-center justify-center rounded-2xl p-6" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
          <div className="flex flex-col items-center gap-1"><div className="flex h-12 w-12 items-center justify-center rounded-full" style={{ backgroundColor: 'rgba(99,102,241,0.15)', border: '2px solid var(--accent-primary)' }}><Server className="h-6 w-6" style={{ color: 'var(--accent-primary)' }} /></div><span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>MYiot Hub</span></div>
          <div className="mt-4 grid grid-cols-4 gap-3">
            {state.devices.map(d => {
              const Icon = typeIcon(d.type);
              return (
                <div key={d.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5" style={{ backgroundColor: 'var(--bg-inset)' }}>
                  <div className={`h-2 w-2 rounded-full ${d.online ? 'bg-emerald-500' : 'bg-gray-600'}`} />
                  <Icon className="h-3 w-3" style={{ color: typeColor(d.type) }} />
                  <span className="truncate text-[11px]" style={{ color: 'var(--text-secondary)' }}>{d.name}</span>
                  <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>{d.ipAddress.split('.').pop()}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Manufacturers */}
      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Manufacturers ({mfrList.length})</h3>
        <div className="grid grid-cols-6 gap-2">
          {mfrList.map(m => (
            <div key={m} className="flex items-center gap-2 rounded-xl px-3 py-2" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
              <Wifi className="h-3 w-3 shrink-0" style={{ color: 'var(--text-muted)' }} /><span className="truncate text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{m}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

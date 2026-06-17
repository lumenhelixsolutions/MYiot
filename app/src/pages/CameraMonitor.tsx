import { useState, useMemo, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Power, EyeOff, Maximize2, X, ChevronLeft, ChevronRight,
  ChevronUp, ChevronDown, ZoomIn, ZoomOut, Focus, Signal,
  ShieldAlert, Check, WifiOff, Play, Square,
} from 'lucide-react';
import { useApp } from '@/store/AppContext';
import WebRtcFeed from '@/components/WebRtcFeed';
import type { CameraLayout, AlertSeverity, AlertType } from '@/types';

const layouts: Array<{ key: CameraLayout; label: string; cols: string }> = [
  { key: '1x1', label: '1', cols: 'grid-cols-1' },
  { key: '2x2', label: '4', cols: 'grid-cols-2' },
  { key: '1+2', label: '1+2', cols: 'grid-cols-3' },
  { key: '2+1', label: '2+1', cols: 'grid-cols-2' },
  { key: '3x3', label: '9', cols: 'grid-cols-3' },
];

const sevColors: Record<AlertSeverity, string> = { info: '#06b6d4', warning: '#f59e0b', critical: '#ef4444' };
const alertTypeLabels: Record<AlertType, string> = { motion: 'Motion', sound: 'Sound', offline: 'Offline', zone_breach: 'Zone' };

function generateId(prefix: string) { return `${prefix}-${Date.now()}-${Math.random().toString(36).substring(2, 5)}`; }

export default function CameraMonitor() {
  const app = useApp();
  const { togglePower, cameras, unackAlerts, removeZone, updateZone, ackAlert, updateRule, addRule, addRecording, backendSync } = app;
  const zones = app.state.zones;
  const alerts = app.state.alerts;
  const alertRules = app.state.alertRules;
  const recordings = app.state.recordings;

  const [layout, setLayout] = useState<CameraLayout>('2x2');
  const [sidebarTab, setSidebarTab] = useState<'controls' | 'zones' | 'alerts' | 'rules' | 'recordings'>('controls');
  const [activeCam, setActiveCam] = useState<string | null>(null);
  const [fullscreenCam, setFullscreenCam] = useState<string | null>(null);
  const [ptz, setPtz] = useState<Record<string, { pan: number; tilt: number; zoom: number }>>({});
  const [alertFilter, setAlertFilter] = useState<AlertSeverity | 'all'>('all');
  const [recordingNow, setRecordingNow] = useState<Record<string, boolean>>({});
  const [now, setNow] = useState(Date.now());

  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);

  const activeCamera = useMemo(() => cameras.find(c => c.id === (fullscreenCam || activeCam)) || cameras[0], [cameras, activeCam, fullscreenCam]);
  const camZones = useMemo(() => zones.filter(z => z.cameraId === activeCamera?.id), [zones, activeCamera]);
  const camAlerts = useMemo(() => {
    const a = alerts.filter(a => a.cameraId === activeCamera?.id);
    return alertFilter === 'all' ? a : a.filter(x => x.severity === alertFilter);
  }, [alerts, activeCamera, alertFilter]);
  const camRules = useMemo(() => alertRules.filter(r => r.cameraId === activeCamera?.id), [alertRules, activeCamera]);
  const camRecordings = useMemo(() => recordings.filter(r => r.cameraId === activeCamera?.id).sort((a, b) => b.startTime - a.startTime), [recordings, activeCamera]);

  const getPtz = useCallback((id: string) => ptz[id] || { pan: 0, tilt: 0, zoom: 1 }, [ptz]);
  const adjPtz = useCallback((id: string, delta: Partial<{ pan: number; tilt: number; zoom: number }>) => {
    setPtz(p => ({ ...p, [id]: { pan: (p[id]?.pan || 0) + (delta.pan || 0), tilt: (p[id]?.tilt || 0) + (delta.tilt || 0), zoom: Math.max(1, Math.min(10, (p[id]?.zoom || 1) + (delta.zoom || 0))) } }));
  }, []);

  const startRec = useCallback((id: string) => {
    addRecording({ id: generateId('rec'), cameraId: id, startTime: Date.now(), triggeredBy: 'manual', sizeMB: 0 });
    setRecordingNow(r => ({ ...r, [id]: true }));
  }, [addRecording]);

  const fmtTime = (ts: number) => { const d = now - ts; if (d < 60000) return 'now'; if (d < 3600000) return `${Math.floor(d / 60000)}m`; if (d < 86400000) return `${Math.floor(d / 3600000)}h`; return `${Math.floor(d / 86400000)}d`; };

  const gridCols = layouts.find(l => l.key === layout)?.cols || 'grid-cols-2';

  const renderFeed = (cam: typeof cameras[0], isLarge?: boolean) => {
    const p = getPtz(cam.id);
    const rec = recordingNow[cam.id];
    const useBackend = backendSync.connected;
    return (
      <div key={cam.id} className={`group relative cursor-pointer overflow-hidden rounded-2xl ${isLarge ? 'col-span-2 row-span-2' : ''}`} style={{ backgroundColor: 'var(--bg-inset)', border: `2px solid ${activeCam === cam.id ? 'var(--accent-primary)' : 'transparent'}` }}
        onClick={() => setActiveCam(cam.id)} onDoubleClick={() => setFullscreenCam(cam.id)}>
        {/* Real WebRTC/MJPEG stream when backend connected, simulated gradient otherwise */}
        {cam.power && cam.online && useBackend ? (
          <WebRtcFeed
            cameraId={cam.id}
            name={cam.name}
            fallbackSrc={`/api/cameras/${cam.id}/mjpeg`}
            enabled={useBackend}
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <div className="absolute inset-0" style={{ background: `radial-gradient(ellipse at ${50 + p.pan}% ${50 + p.tilt}%, rgba(30,30,50,0.8) 0%, rgba(10,10,20,0.95) 100%)` }}>
            <div className="absolute inset-0" style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.01) 2px, rgba(255,255,255,0.01) 4px)' }} />
          </div>
        )}
        {!cam.online && <div className="absolute inset-0 flex flex-col items-center justify-center gap-2" style={{ backgroundColor: 'rgba(8,8,16,0.9)' }}><WifiOff className="h-8 w-8" style={{ color: 'var(--text-muted)' }} /><span className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>OFFLINE</span></div>}
        {!cam.power && cam.online && <div className="absolute inset-0 flex flex-col items-center justify-center gap-2" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}><EyeOff className="h-8 w-8" style={{ color: 'var(--text-muted)' }} /><span className="text-sm font-medium text-white">Privacy Mode</span></div>}
        {cam.power && cam.online && (
          <>
            <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-full px-2 py-0.5" style={{ backgroundColor: 'rgba(239,68,68,0.8)' }}>
              <div className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /><span className="text-[10px] font-bold text-white">LIVE</span>
            </div>
            {rec && <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full px-2 py-0.5" style={{ backgroundColor: 'rgba(239,68,68,0.6)' }}><div className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /><span className="text-[10px] font-bold text-white">REC</span></div>}
            <span className="absolute bottom-3 right-3 font-mono text-[10px]" style={{ color: 'rgba(255,255,255,0.5)' }}>{new Date(now).toLocaleTimeString()}</span>
          </>
        )}
        <div className="absolute bottom-3 left-3 flex items-center gap-2">
          <span className="text-xs font-semibold text-white">{cam.name}</span>
          <div className={`h-1.5 w-1.5 rounded-full ${cam.online ? 'bg-emerald-500' : 'bg-gray-600'}`} />
        </div>
        <div className="absolute right-3 top-10 opacity-0 transition-opacity group-hover:opacity-100">
          <div className="flex flex-col gap-1">
            <button onClick={e => { e.stopPropagation(); setFullscreenCam(cam.id); }} className="flex h-7 w-7 items-center justify-center rounded-lg bg-black/50 text-white hover:bg-black/70"><Maximize2 className="h-3.5 w-3.5" /></button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-full gap-4">
      {/* Main */}
      <div className="flex flex-1 flex-col gap-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {layouts.map(l => (
              <button key={l.key} onClick={() => setLayout(l.key)} className="rounded-lg px-3 py-1.5 text-xs font-medium transition-all" style={{ backgroundColor: layout === l.key ? 'var(--accent-primary)' : 'var(--bg-surface)', color: layout === l.key ? '#fff' : 'var(--text-muted)', border: `1px solid ${layout === l.key ? 'var(--accent-primary)' : 'var(--border-subtle)'}` }}>{l.label}</button>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{cameras.filter(c => c.online).length}/{cameras.length} online</span>
            {unackAlerts.length > 0 && <button onClick={() => setSidebarTab('alerts')} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium" style={{ backgroundColor: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}><ShieldAlert className="h-3.5 w-3.5" />{unackAlerts.length} alert{unackAlerts.length > 1 ? 's' : ''}</button>}
          </div>
        </div>

        {/* Grid */}
        <div className={`grid ${gridCols} gap-3`} style={{ aspectRatio: layout === '1x1' ? '16/9' : undefined }}>
          {layout === '1+2' && cameras[0] && <>{renderFeed(cameras[0], true)}{cameras.slice(1, 3).map(c => renderFeed(c))}</>}
          {layout === '2+1' && cameras[2] && <>{cameras.slice(0, 2).map(c => renderFeed(c))}{renderFeed(cameras[2], true)}</>}
          {layout !== '1+2' && layout !== '2+1' && cameras.slice(0, layout === '3x3' ? 9 : layout === '1x1' ? 1 : 4).map(c => renderFeed(c))}
        </div>
      </div>

      {/* Sidebar */}
      <div className="flex w-80 flex-col gap-3 overflow-y-auto rounded-2xl p-4" style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)' }}>
        {/* Camera selector */}
        <div className="flex gap-1 overflow-x-auto pb-1">
          {cameras.map(c => (
            <button key={c.id} onClick={() => setActiveCam(c.id)} className="flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-medium transition-all" style={{ backgroundColor: activeCamera?.id === c.id ? 'var(--accent-primary)' : 'var(--bg-elevated)', color: activeCamera?.id === c.id ? '#fff' : 'var(--text-muted)', border: `1px solid ${activeCamera?.id === c.id ? 'var(--accent-primary)' : 'var(--border-subtle)'}` }}>
              <div className={`h-1.5 w-1.5 rounded-full ${c.online ? 'bg-emerald-500' : 'bg-gray-600'}`} />{c.name}</button>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b pb-2" style={{ borderColor: 'var(--border-subtle)' }}>
          {(['controls', 'zones', 'alerts', 'rules', 'recordings'] as const).map(t => (
            <button key={t} onClick={() => setSidebarTab(t)} className="rounded-md px-2 py-1 text-[10px] font-medium capitalize transition-all" style={{ color: sidebarTab === t ? 'var(--accent-primary)' : 'var(--text-muted)' }}>{t}</button>
          ))}
        </div>

        {/* Tab Content */}
        {sidebarTab === 'controls' && activeCamera && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{activeCamera.name}</span>
              <div className="flex items-center gap-1"><Signal className="h-3 w-3" style={{ color: activeCamera.signalStrength > 70 ? '#10b981' : '#f59e0b' }} /><span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{activeCamera.signalStrength}%</span></div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => togglePower(activeCamera.id)} className="flex flex-1 items-center justify-center gap-1 rounded-lg py-2 text-xs font-medium text-white transition-opacity hover:opacity-90" style={{ backgroundColor: activeCamera.power ? '#ef4444' : 'var(--accent-primary)' }}><Power className="h-3.5 w-3.5" />{activeCamera.power ? 'Stop' : 'Start'}</button>
              <button onClick={() => recordingNow[activeCamera.id] ? (() => { setRecordingNow(r => ({ ...r, [activeCamera.id]: false })); })() : startRec(activeCamera.id)} className="flex flex-1 items-center justify-center gap-1 rounded-lg py-2 text-xs font-medium transition-all" style={{ backgroundColor: recordingNow[activeCamera.id] ? 'rgba(239,68,68,0.15)' : 'var(--bg-elevated)', color: recordingNow[activeCamera.id] ? '#ef4444' : 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}>{recordingNow[activeCamera.id] ? <><Square className="h-3.5 w-3.5" />Stop</> : <><Play className="h-3.5 w-3.5" />Record</>}</button>
            </div>
            {/* PTZ */}
            <div className="flex flex-col items-center gap-1">
              <span className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>PTZ</span>
              <button onClick={() => adjPtz(activeCamera.id, { tilt: -5 })} className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}><ChevronUp className="h-4 w-4" style={{ color: 'var(--text-secondary)' }} /></button>
              <div className="flex gap-1">
                <button onClick={() => adjPtz(activeCamera.id, { pan: -5 })} className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}><ChevronLeft className="h-4 w-4" style={{ color: 'var(--text-secondary)' }} /></button>
                <button onClick={() => setPtz(p => ({ ...p, [activeCamera.id]: { pan: 0, tilt: 0, zoom: 1 } }))} className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}><Focus className="h-4 w-4" style={{ color: 'var(--text-secondary)' }} /></button>
                <button onClick={() => adjPtz(activeCamera.id, { pan: 5 })} className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}><ChevronRight className="h-4 w-4" style={{ color: 'var(--text-secondary)' }} /></button>
              </div>
              <button onClick={() => adjPtz(activeCamera.id, { tilt: 5 })} className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}><ChevronDown className="h-4 w-4" style={{ color: 'var(--text-secondary)' }} /></button>
              <div className="mt-1 flex gap-2">
                <button onClick={() => adjPtz(activeCamera.id, { zoom: -0.5 })} className="flex h-7 w-7 items-center justify-center rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}><ZoomOut className="h-3.5 w-3.5" style={{ color: 'var(--text-secondary)' }} /></button>
                <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>{getPtz(activeCamera.id).zoom.toFixed(1)}x</span>
                <button onClick={() => adjPtz(activeCamera.id, { zoom: 0.5 })} className="flex h-7 w-7 items-center justify-center rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}><ZoomIn className="h-3.5 w-3.5" style={{ color: 'var(--text-secondary)' }} /></button>
              </div>
            </div>
            {/* Info */}
            <div className="rounded-lg p-2" style={{ backgroundColor: 'var(--bg-inset)' }}>
              {[{ l: 'IP', v: activeCamera.ipAddress }, { l: 'Protocol', v: activeCamera.protocol }, { l: 'Firmware', v: activeCamera.firmware }].map(i => (
                <div key={i.l} className="flex justify-between py-0.5"><span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{i.l}</span><span className="font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>{i.v}</span></div>
              ))}
            </div>

            {/* Live snapshot */}
            <div className="rounded-lg p-2" style={{ backgroundColor: 'var(--bg-inset)' }}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-medium" style={{ color: 'var(--text-muted)' }}>Snapshot</span>
                <button
                  onClick={() => setNow(Date.now())}
                  className="text-[10px]"
                  style={{ color: 'var(--accent-primary)' }}
                >Refresh</button>
              </div>
              {activeCamera.online && activeCamera.power ? (
                <img
                  key={now}
                  src={`/api/cameras/${activeCamera.id}/snapshot?ts=${now}`}
                  alt={`${activeCamera.name} snapshot`}
                  className="mt-2 h-32 w-full rounded-lg object-cover"
                />
              ) : (
                <div className="mt-2 flex h-32 items-center justify-center rounded-lg" style={{ backgroundColor: 'var(--bg-elevated)' }}>
                  <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Camera offline</span>
                </div>
              )}
            </div>
          </div>
        )}

        {sidebarTab === 'zones' && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between"><span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>Zones ({camZones.length})</span></div>
            {camZones.map(z => (
              <div key={z.id} className="rounded-lg p-2" style={{ backgroundColor: 'var(--bg-inset)' }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2"><div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: z.color }} /><span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{z.name}</span></div>
                  <button onClick={() => removeZone(z.id)} className="rounded p-1 hover:bg-white/5"><X className="h-3 w-3" style={{ color: 'var(--text-muted)' }} /></button>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <button onClick={() => updateZone(z.id, { motionEnabled: !z.motionEnabled })} className="flex h-4 w-7 items-center rounded-full p-0.5 transition-all" style={{ backgroundColor: z.motionEnabled ? 'var(--accent-primary)' : 'var(--bg-elevated)' }}><motion.div layout className="h-3 w-3 rounded-full bg-white" style={{ marginLeft: z.motionEnabled ? 10 : 0 }} /></button>
                  <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Sens: {z.sensitivity}%</span>
                  <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>Trig: {z.triggerCount}</span>
                </div>
              </div>
            ))}
            {camZones.length === 0 && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>No zones for this camera</p>}
          </div>
        )}

        {sidebarTab === 'alerts' && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <div className="flex gap-1">
                {(['all', 'info', 'warning', 'critical'] as const).map(f => (
                  <button key={f} onClick={() => setAlertFilter(f)} className="rounded px-1.5 py-0.5 text-[10px] font-medium capitalize" style={{ color: alertFilter === f ? '#fff' : 'var(--text-muted)', backgroundColor: alertFilter === f ? 'var(--accent-primary)' : 'transparent' }}>{f === 'all' ? 'All' : f}</button>
                ))}
              </div>
              <button onClick={() => camAlerts.forEach(a => { if (!a.acknowledged) ackAlert(a.id); })} className="text-[10px]" style={{ color: 'var(--accent-primary)' }}>Ack All</button>
            </div>
            {camAlerts.map(a => (
              <div key={a.id} className="rounded-lg p-2" style={{ backgroundColor: a.acknowledged ? 'var(--bg-inset)' : `${sevColors[a.severity]}08`, border: `1px solid ${a.acknowledged ? 'transparent' : `${sevColors[a.severity]}20`}` }}>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full" style={{ backgroundColor: sevColors[a.severity] }} />
                  <span className="flex-1 text-[11px]" style={{ color: 'var(--text-primary)' }}>{a.message}</span>
                  {!a.acknowledged && <button onClick={() => ackAlert(a.id)} className="rounded p-0.5 hover:bg-white/5"><Check className="h-3 w-3" style={{ color: '#10b981' }} /></button>}
                </div>
                <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{fmtTime(a.timestamp)} ago · {alertTypeLabels[a.type]}</span>
              </div>
            ))}
            {camAlerts.length === 0 && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>No alerts</p>}
          </div>
        )}

        {sidebarTab === 'rules' && (
          <div className="flex flex-col gap-2">
            {camRules.map(r => (
              <div key={r.id} className="rounded-lg p-2" style={{ backgroundColor: 'var(--bg-inset)' }}>
                <div className="flex items-center justify-between"><span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{alertTypeLabels[r.type]}</span>
                  <button onClick={() => updateRule(r.id, { enabled: !r.enabled })} className="flex h-4 w-7 items-center rounded-full p-0.5 transition-all" style={{ backgroundColor: r.enabled ? 'var(--accent-primary)' : 'var(--bg-elevated)' }}><motion.div layout className="h-3 w-3 rounded-full bg-white" style={{ marginLeft: r.enabled ? 10 : 0 }} /></button>
                </div>
                <div className="mt-1 flex gap-2 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  <span>Sens: {r.sensitivity}%</span><span>CD: {r.cooldownSeconds}s</span>
                </div>
              </div>
            ))}
            <button onClick={() => addRule({ id: generateId('rule'), cameraId: activeCamera?.id || '', type: 'motion', enabled: true, sensitivity: 75, cooldownSeconds: 30, notifyPush: true, notifyEmail: false, soundEnabled: true })} className="mt-1 rounded-lg py-1.5 text-xs font-medium text-white" style={{ backgroundColor: 'var(--accent-primary)' }}>+ Add Rule</button>
          </div>
        )}

        {sidebarTab === 'recordings' && (
          <div className="flex flex-col gap-2">
            {camRecordings.map(rec => (
              <div key={rec.id} className="rounded-lg p-2" style={{ backgroundColor: 'var(--bg-inset)' }}>
                <div className="flex items-center justify-between"><span className="font-mono text-[10px]" style={{ color: 'var(--text-secondary)' }}>{new Date(rec.startTime).toLocaleTimeString()}</span>
                  <span className="rounded px-1.5 py-0.5 text-[9px] font-medium" style={{ backgroundColor: rec.triggeredBy === 'manual' ? 'rgba(99,102,241,0.1)' : 'rgba(245,158,11,0.1)', color: rec.triggeredBy === 'manual' ? 'var(--accent-primary)' : '#f59e0b' }}>{rec.triggeredBy}</span>
                </div>
                <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{rec.sizeMB.toFixed(1)} MB{rec.endTime ? ` · ${Math.floor((rec.endTime - rec.startTime) / 1000)}s` : ' · Recording...'}</span>
              </div>
            ))}
            {camRecordings.length === 0 && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>No recordings</p>}
          </div>
        )}
      </div>

      {/* Fullscreen */}
      <AnimatePresence>{fullscreenCam && (() => {
        const cam = cameras.find(c => c.id === fullscreenCam); if (!cam) return null; const p = getPtz(cam.id);
        return (
          <motion.div key="fs" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[200] flex flex-col" style={{ backgroundColor: 'var(--bg-base)' }}>
            <div className="flex h-14 items-center justify-between px-6" style={{ backgroundColor: 'rgba(7,7,13,0.9)' }}>
              <div className="flex items-center gap-3"><span className="text-sm font-semibold text-white">{cam.name}</span><div className="flex items-center gap-1 rounded-full px-2 py-0.5" style={{ backgroundColor: 'rgba(239,68,68,0.7)' }}><div className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /><span className="text-[10px] font-bold text-white">LIVE</span></div></div>
              <button onClick={() => setFullscreenCam(null)} className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10"><X className="h-5 w-5 text-white" /></button>
            </div>
            <div className="relative flex-1" style={{ backgroundColor: 'var(--bg-base)' }}>
              {backendSync.connected ? (
                <WebRtcFeed
                  cameraId={cam.id}
                  name={cam.name}
                  fallbackSrc={`/api/cameras/${cam.id}/mjpeg`}
                  enabled={backendSync.connected}
                  className="absolute inset-0 h-full w-full object-cover"
                />
              ) : (
                <div className="absolute inset-0" style={{ background: `radial-gradient(ellipse at ${50 + p.pan}% ${50 + p.tilt}%, rgba(30,30,50,0.8) 0%, rgba(10,10,20,0.95) 100%)` }}>
                  <div className="absolute inset-0" style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,255,255,0.01) 2px, rgba(255,255,255,0.01) 4px)' }} />
                </div>
              )}
              <div className="absolute bottom-8 left-1/2 flex -translate-x-1/2 items-center gap-3 rounded-2xl px-4 py-2" style={{ backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}>
                <button onClick={() => adjPtz(cam.id, { tilt: -5 })} className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10"><ChevronUp className="h-4 w-4 text-white" /></button>
                <button onClick={() => adjPtz(cam.id, { pan: -5 })} className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10"><ChevronLeft className="h-4 w-4 text-white" /></button>
                <button onClick={() => setPtz(p => ({ ...p, [cam.id]: { pan: 0, tilt: 0, zoom: 1 } }))} className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10"><Focus className="h-4 w-4 text-white" /></button>
                <button onClick={() => adjPtz(cam.id, { pan: 5 })} className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10"><ChevronRight className="h-4 w-4 text-white" /></button>
                <button onClick={() => adjPtz(cam.id, { tilt: 5 })} className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10"><ChevronDown className="h-4 w-4 text-white" /></button>
                <div className="mx-2 h-6 w-px bg-white/20" />
                <button onClick={() => adjPtz(cam.id, { zoom: -0.5 })} className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10"><ZoomOut className="h-4 w-4 text-white" /></button>
                <span className="font-mono text-xs text-white">{p.zoom.toFixed(1)}x</span>
                <button onClick={() => adjPtz(cam.id, { zoom: 0.5 })} className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-white/10"><ZoomIn className="h-4 w-4 text-white" /></button>
              </div>
            </div>
          </motion.div>
        );
      })()}</AnimatePresence>
    </div>
  );
}

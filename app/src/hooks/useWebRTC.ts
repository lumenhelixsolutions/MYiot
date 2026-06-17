import { useEffect, useRef, useState } from 'react';
import { api } from '@/api/client';

const ICE_SERVERS: RTCConfiguration = {
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
};

function waitForIceGathering(pc: RTCPeerConnection): Promise<void> {
  return new Promise((resolve) => {
    if (pc.iceGatheringState === 'complete') {
      resolve();
      return;
    }
    const checkState = () => {
      if (pc.iceGatheringState === 'complete') {
        pc.removeEventListener('icegatheringstatechange', checkState);
        resolve();
      }
    };
    pc.addEventListener('icegatheringstatechange', checkState);
    // Fallback: most candidates are gathered within a few seconds
    setTimeout(() => {
      pc.removeEventListener('icegatheringstatechange', checkState);
      resolve();
    }, 2500);
  });
}

/**
 * Hook that establishes a WebRTC video stream for a camera.
 *
 * Returns a ref that should be attached to a <video> element. The hook
 * attempts to negotiate a WebRTC session with the backend; if it fails,
 * `active` remains false so the caller can fall back to MJPEG.
 */
export function useWebRTC(cameraId: string | null | undefined, enabled = true) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!cameraId || !enabled) {
      setActive(false);
      setError(null);
      return;
    }

    let cancelled = false;
    const pc = new RTCPeerConnection(ICE_SERVERS);
    pcRef.current = pc;

    pc.addEventListener('track', (event) => {
      if (cancelled || !videoRef.current || event.streams.length === 0) return;
      videoRef.current.srcObject = event.streams[0];
      setActive(true);
      setError(null);
    });

    pc.addEventListener('connectionstatechange', () => {
      if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
        setActive(false);
        if (!cancelled) setError('WebRTC connection failed');
      }
    });

    async function negotiate() {
      try {
        if (!cameraId) throw new Error('No camera selected');

        // Request a recv-only video track
        pc.addTransceiver('video', { direction: 'recvonly' });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        await waitForIceGathering(pc);

        if (cancelled) return;

        const localDesc = pc.localDescription;
        if (!localDesc) throw new Error('No local description');

        const res = await api.sendWebRtcOffer(cameraId, localDesc.sdp);
        if (!res.ok || !res.data) {
          throw new Error(res.error || 'WebRTC offer failed');
        }

        const answer = res.data as { type: string; sdp: string };
        await pc.setRemoteDescription(
          new RTCSessionDescription({ type: 'answer', sdp: answer.sdp })
        );
      } catch (err) {
        if (cancelled) return;
        setActive(false);
        setError(err instanceof Error ? err.message : 'WebRTC error');
      }
    }

    negotiate();

    return () => {
      cancelled = true;
      pc.close();
      pcRef.current = null;
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
    };
  }, [cameraId, enabled]);

  return { videoRef, active, error };
}

import { useWebRTC } from '@/hooks/useWebRTC';

interface WebRtcFeedProps {
  cameraId: string;
  name: string;
  className?: string;
  fallbackSrc: string;
  enabled?: boolean;
}

/**
 * Camera feed that prefers WebRTC and falls back to MJPEG.
 *
 * WebRTC gives lower latency, but it requires go2rtc to be running and
 * reachable. If negotiation fails or the connection drops, the component
 * renders the MJPEG fallback instead.
 */
export default function WebRtcFeed({
  cameraId,
  name,
  className = '',
  fallbackSrc,
  enabled = true,
}: WebRtcFeedProps) {
  const { videoRef, active, error } = useWebRTC(cameraId, enabled);

  if (!active) {
    return (
      <img
        src={fallbackSrc}
        alt={name}
        className={className}
        style={{ imageRendering: 'auto' }}
      />
    );
  }

  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      muted
      className={className}
      title={error || name}
    />
  );
}

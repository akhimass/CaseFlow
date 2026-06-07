'use client';

import { useEffect } from 'react';
import { type LocalParticipant, RoomEvent, Track } from 'livekit-client';
import { toast } from 'sonner';
import { useLocalParticipant, useRoomContext } from '@livekit/components-react';

const textDecoder = new TextDecoder();
const textEncoder = new TextEncoder();

type CaptureRequest = {
  case_id?: string;
  doc_type?: string;
  turn?: number;
  matched_phrase?: string;
};

const DOC_LABELS: Record<string, { en: string; es: string }> = {
  police_report: { en: 'police report', es: 'reporte policial' },
  er_discharge: { en: 'hospital discharge papers', es: 'papeles del hospital' },
  insurance: { en: 'insurance document', es: 'documento del seguro' },
};

function docLabel(docType: string, lang: string): string {
  const labels = DOC_LABELS[docType] ?? { en: 'document', es: 'documento' };
  return lang.startsWith('es') ? labels.es : labels.en;
}

// Cap the longest side so a full-res phone frame (often 1920px+) doesn't make
// Unsiloed parsing crawl. ~1100px keeps document text legible for OCR while
// cutting parse time substantially.
const MAX_FRAME_PX = 1100;

async function captureLocalVideoFrame(videoElement: HTMLVideoElement): Promise<string | null> {
  const vw = videoElement.videoWidth;
  const vh = videoElement.videoHeight;
  if (!vw || !vh) {
    return null;
  }

  const scale = Math.min(1, MAX_FRAME_PX / Math.max(vw, vh));
  const width = Math.round(vw * scale);
  const height = Math.round(vh * scale);

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return null;
  }
  ctx.drawImage(videoElement, 0, 0, width, height);
  return canvas.toDataURL('image/jpeg', 0.86);
}

function findLocalVideoElement(): HTMLVideoElement | null {
  const videos = Array.from(document.querySelectorAll('video'));
  for (const video of videos) {
    if (video.readyState >= 2 && video.videoWidth > 0) {
      return video;
    }
  }
  return videos[0] ?? null;
}

function isCameraOn(localParticipant: LocalParticipant) {
  const pub = localParticipant.getTrackPublication(Track.Source.Camera);
  return Boolean(pub && !pub.isMuted && pub.track);
}

async function ensureCameraEnabled(
  localParticipant: LocalParticipant,
  docType: string
): Promise<boolean> {
  if (isCameraOn(localParticipant)) {
    return true;
  }

  const lang = typeof navigator !== 'undefined' ? navigator.language : 'en';
  const label = docLabel(docType, lang);
  const isEs = lang.toLowerCase().startsWith('es');

  toast.message(isEs ? 'Encienda su cámara' : 'Turn on your camera', {
    description: isEs
      ? `El especialista necesita ver su ${label}. Toque el ícono de cámara abajo o permita el acceso.`
      : `The specialist needs to see your ${label}. Tap the camera button below or allow access.`,
    duration: 8000,
  });

  try {
    await localParticipant.setCameraEnabled(true);
  } catch (error) {
    console.warn('Could not enable camera', error);
    return false;
  }

  // Give the track a moment to publish before capture.
  await new Promise((resolve) => setTimeout(resolve, 1200));
  return isCameraOn(localParticipant);
}

/**
 * Listens for agent `enable_video` / `capture_document` requests and returns a
 * camera JPEG frame over the LiveKit data channel as `document_frame`.
 */
export function useDocumentCapture() {
  const room = useRoomContext();
  const { localParticipant } = useLocalParticipant();

  useEffect(() => {
    if (!room || !localParticipant) return;

    const handleData = async (payload: Uint8Array) => {
      try {
        const message = JSON.parse(textDecoder.decode(payload)) as {
          type?: string;
          data?: CaptureRequest;
        };
        const docType = message.data?.doc_type ?? '';

        if (message.type === 'enable_video' && docType) {
          await ensureCameraEnabled(localParticipant, docType);
          return;
        }

        if (message.type !== 'capture_document' || !docType) {
          return;
        }

        const cameraReady = await ensureCameraEnabled(localParticipant, docType);
        if (!cameraReady) {
          return;
        }

        const video = findLocalVideoElement();
        if (!video) {
          return;
        }

        const imageBase64 = await captureLocalVideoFrame(video);
        if (!imageBase64) {
          return;
        }

        const response = {
          type: 'document_frame',
          data: {
            case_id: message.data?.case_id,
            doc_type: docType,
            turn: message.data?.turn,
            image_base64: imageBase64,
          },
        };

        await localParticipant.publishData(textEncoder.encode(JSON.stringify(response)), {
          reliable: true,
        });
      } catch (error) {
        console.warn('Document capture failed', error);
      }
    };

    room.on(RoomEvent.DataReceived, handleData);
    return () => {
      room.off(RoomEvent.DataReceived, handleData);
    };
  }, [room, localParticipant]);
}

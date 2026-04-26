"use client";
import { useState, useRef } from "react";
import { Mic, Square } from "lucide-react";
import { getAccessToken, API_BASE } from "@/lib/api/client";

interface VoiceRecorderProps {
  onTranscription: (text: string) => void;
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const numSamples = samples.length;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);
  const write = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + numSamples * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);        // PCM
  view.setUint16(22, 1, true);        // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, numSamples * 2, true);
  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export function VoiceRecorder({ onTranscription }: VoiceRecorderProps) {
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    chunksRef.current = [];

    const recorder = new MediaRecorder(stream);
    recorderRef.current = recorder;
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.start(100);
    setRecording(true);
  };

  const stopRecording = async () => {
    setRecording(false);
    const recorder = recorderRef.current;
    if (!recorder) return;

    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
      recorder.stop();
    });
    streamRef.current?.getTracks().forEach(t => t.stop());

    setProcessing(true);
    try {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
      const arrayBuffer = await blob.arrayBuffer();

      // Decode in browser (handles whatever format MediaRecorder used)
      const audioCtx = new AudioContext();
      const decoded = await audioCtx.decodeAudioData(arrayBuffer);
      await audioCtx.close();

      // Resample to mono 16 kHz via OfflineAudioContext
      const TARGET_RATE = 16000;
      const offlineCtx = new OfflineAudioContext(
        1,
        Math.ceil(decoded.duration * TARGET_RATE),
        TARGET_RATE,
      );
      const src = offlineCtx.createBufferSource();
      src.buffer = decoded;
      src.connect(offlineCtx.destination);
      src.start();
      const rendered = await offlineCtx.startRendering();
      const pcm = rendered.getChannelData(0);

      const wav = encodeWav(pcm, TARGET_RATE);
      const form = new FormData();
      form.append("file", wav, "recording.wav");

      const token = getAccessToken();
      const res = await fetch(`${API_BASE}/api/v1/ai/transcribe`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      if (res.ok) {
        const data = await res.json() as { text: string };
        if (data.text) onTranscription(data.text);
      }
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {!recording ? (
        <button
          type="button"
          onClick={() => void startRecording()}
          className="flex items-center gap-2 px-3 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Mic size={16} />
          Aufnehmen
        </button>
      ) : (
        <button
          type="button"
          onClick={() => void stopRecording()}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-800 text-white rounded-lg text-sm font-medium transition-colors animate-pulse"
        >
          <Square size={16} />
          Stopp
        </button>
      )}
      {processing && <span className="text-sm text-[var(--ink-faint)]">Verarbeite...</span>}
    </div>
  );
}

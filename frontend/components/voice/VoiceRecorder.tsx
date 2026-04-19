"use client";
import { useState, useRef } from "react";
import { Mic, Square } from "lucide-react";
import { getAccessToken, API_BASE } from "@/lib/api/client";

interface VoiceRecorderProps {
  onTranscription: (text: string) => void;
}

/** Encode raw PCM samples (Float32, mono) as a 16-bit PCM WAV blob. */
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
  view.setUint32(16, 16, true);       // subchunk1 size
  view.setUint16(20, 1, true);        // PCM
  view.setUint16(22, 1, true);        // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true);        // block align
  view.setUint16(34, 16, true);       // bits per sample
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
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const samplesRef = useRef<Float32Array[]>([]);

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    samplesRef.current = [];

    const ctx = new AudioContext({ sampleRate: 16000 });
    audioCtxRef.current = ctx;
    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      const data = e.inputBuffer.getChannelData(0);
      samplesRef.current.push(new Float32Array(data));
    };

    source.connect(processor);
    processor.connect(ctx.destination);
    setRecording(true);
  };

  const stopRecording = async () => {
    setRecording(false);
    processorRef.current?.disconnect();
    audioCtxRef.current?.close();
    streamRef.current?.getTracks().forEach(t => t.stop());

    setProcessing(true);
    try {
      const allSamples = samplesRef.current;
      const total = allSamples.reduce((n, s) => n + s.length, 0);
      const merged = new Float32Array(total);
      let offset = 0;
      for (const chunk of allSamples) { merged.set(chunk, offset); offset += chunk.length; }

      const wav = encodeWav(merged, 16000);
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

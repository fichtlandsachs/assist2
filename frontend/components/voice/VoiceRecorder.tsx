"use client";
import { useState, useRef } from "react";
import { Mic, Square } from "lucide-react";
import { getAccessToken } from "@/lib/api/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface VoiceRecorderProps {
  onTranscription: (text: string) => void;
}

export function VoiceRecorder({ onTranscription }: VoiceRecorderProps) {
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorderRef.current = mediaRecorder;
    chunksRef.current = [];
    mediaRecorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    mediaRecorder.onstop = async () => {
      setProcessing(true);
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const form = new FormData();
      form.append("file", blob, "recording.webm");
      try {
        const token = getAccessToken();
        const res = await fetch(`${API_BASE}/api/v1/ai/transcribe`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: form,
          // No Content-Type header — browser sets multipart boundary automatically
        });
        if (res.ok) {
          const data = await res.json() as { text: string };
          onTranscription(data.text);
        } else {
          onTranscription("");
        }
      } catch {
        onTranscription("");
      } finally {
        setProcessing(false);
        stream.getTracks().forEach(t => t.stop());
      }
    };
    mediaRecorder.start();
    setRecording(true);
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
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
          onClick={stopRecording}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-800 text-white rounded-lg text-sm font-medium transition-colors animate-pulse"
        >
          <Square size={16} />
          Stopp
        </button>
      )}
      {processing && <span className="text-sm text-slate-500">Verarbeite...</span>}
    </div>
  );
}

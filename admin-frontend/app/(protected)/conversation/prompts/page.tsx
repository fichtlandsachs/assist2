"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listPromptTemplates,
  createPromptTemplate,
  type PromptTemplate,
} from "@/lib/api";

export default function Page() {
  const [items, setItems] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setError(null);
      const data = await listPromptTemplates();
      setItems(data);
    } catch (e: any) {
      setError(e?.message || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Prompt-Vorlagen</h1>
          <p className="text-sm text-gray-500 mt-1">
            System- und User-Prompts für die Conversation Engine
          </p>
        </div>
        <Link
          href="/conversation/help#prompts"
          className="border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50"
        >
          Hilfe
        </Link>
      </div>

      {loading ? (
        <p className="text-gray-500">Lade…</p>
      ) : error ? (
        <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
          <p className="text-yellow-800">⚠️ {error}</p>
          <button
            onClick={() => {
              setLoading(true);
              void load();
            }}
            className="mt-3 text-sm text-yellow-700 underline"
          >
            Erneut versuchen
          </button>
        </div>
      ) : items.length === 0 ? (
        <p className="text-gray-500">Keine Einträge vorhanden.</p>
      ) : (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b last:border-0">
                  <td className="px-4 py-3">{item.name || item.key}</td>
                  <td className="px-4 py-3">
                    {item.is_active ? (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                        Aktiv
                      </span>
                    ) : (
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                        Inaktiv
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

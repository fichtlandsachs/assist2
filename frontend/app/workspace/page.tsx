'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  FileText, ChevronDown, ChevronRight, AlertTriangle,
  CheckCircle2, Circle, MoreHorizontal, Plus, Download,
  Send, Lightbulb, Link2, Clock, Shield, Activity,
  BookOpen, Trash2, GripVertical
} from 'lucide-react';

// ─── Types ───────────────────────────────────────────────────────────────────

type DerivationStatus = 'DIRECT' | 'INTERPRETED' | 'OPEN';
type SectionStatus = 'complete' | 'partial' | 'open';

interface Section {
  id: string;
  title: string;
  content: string;
  status: SectionStatus;
  derivation: DerivationStatus;
  confidence: number | null;
  source: string | null;
  required: boolean;
  expanded: boolean;
}

interface OpenPoint {
  id: string;
  section: string;
  description: string;
  severity: 'high' | 'medium' | 'low';
}

// ─── Mock Data ────────────────────────────────────────────────────────────────

const INITIAL_SECTIONS: Section[] = [
  {
    id: 'purpose',
    title: '1. Zweck',
    content: 'Dieser Prozess definiert die Vorgehensweise zur Wiederherstellung kritischer Datenbankdienste nach einem Ausfall. Er gilt für alle produktiven PostgreSQL-Instanzen der Plattform.',
    status: 'complete',
    derivation: 'DIRECT',
    confidence: 0.94,
    source: 'PROJ-142: Als Betriebsteam müssen wir den DB-Wiederherstellungsprozess dokumentieren.',
    required: true,
    expanded: true,
  },
  {
    id: 'scope',
    title: '2. Geltungsbereich',
    content: 'Gilt für: PostgreSQL 16 (Core DB), pgvector-Instanz, Redis-Cluster. Nicht enthalten: MongoDB-Archiv (separates Runbook).',
    status: 'complete',
    derivation: 'DIRECT',
    confidence: 0.88,
    source: 'PROJ-143: System-Architekturdiagramm v2.4',
    required: true,
    expanded: false,
  },
  {
    id: 'roles',
    title: '3. Rollen & Verantwortlichkeiten',
    content: '| Rolle | Aufgabe |\n|---|---|\n| DB-Admin | Ausführung Recovery-Schritte |\n| Incident Manager | Koordination & Kommunikation |\n| IT-Leitung | Eskalation & Freigabe |',
    status: 'partial',
    derivation: 'INTERPRETED',
    confidence: 0.71,
    source: 'PROJ-144 – Rollenstruktur aus Organigramm abgeleitet',
    required: true,
    expanded: false,
  },
  {
    id: 'process_flow',
    title: '4. Prozessablauf',
    content: '',
    status: 'open',
    derivation: 'OPEN',
    confidence: null,
    source: null,
    required: true,
    expanded: true,
  },
  {
    id: 'exceptions',
    title: '5. Ausnahmen',
    content: '',
    status: 'open',
    derivation: 'OPEN',
    confidence: null,
    source: null,
    required: true,
    expanded: false,
  },
  {
    id: 'risks',
    title: '6. Risiken',
    content: '- Datenverlust bei verzögertem RPO-Überschreiten\n- Fehlkonfiguration nach Restore\n- Abhängigkeit von Backup-Verfügbarkeit',
    status: 'complete',
    derivation: 'DIRECT',
    confidence: 0.91,
    source: 'PROJ-145: Risikobewertung Q1/2026',
    required: true,
    expanded: false,
  },
  {
    id: 'controls',
    title: '7. Controls',
    content: '- Tägliche Backup-Verifikation\n- Monatliche Recovery-Tests\n- Monitoring-Alert bei RPO-Überschreitung',
    status: 'complete',
    derivation: 'DIRECT',
    confidence: 0.87,
    source: 'PROJ-146: Control-Framework',
    required: true,
    expanded: false,
  },
  {
    id: 'compliance',
    title: '8. Compliance-Mapping',
    content: '| Anforderung | Framework | Status |\n|---|---|---|\n| Business Continuity | NIS2 Art.21 | PARTIAL |\n| Incident Handling | NIS2 Art.21 | MET |\n| Recovery Prozesse | KRITIS | PARTIAL |',
    status: 'partial',
    derivation: 'INTERPRETED',
    confidence: 0.73,
    source: 'NIS2-Anforderungskatalog v2024',
    required: true,
    expanded: false,
  },
];

const OPEN_POINTS: OpenPoint[] = [
  { id: 'op1', section: 'Prozessablauf', description: 'Schrittfolge für Cold-Restore fehlt vollständig', severity: 'high' },
  { id: 'op2', section: 'Ausnahmen', description: 'Ausnahmeregeln nicht aus Input ableitbar', severity: 'medium' },
];

// ─── Sub-Components ───────────────────────────────────────────────────────────

function DerivationBadge({ status, confidence }: { status: DerivationStatus; confidence: number | null }) {
  const map = {
    DIRECT:      { label: 'DIRECT',      cls: 'bg-[#00D4AA] text-[#0A0A0A]' },
    INTERPRETED: { label: 'INTERPRETED', cls: 'bg-[#FFD700] text-[#0A0A0A]' },
    OPEN:        { label: 'OFFEN',       cls: 'bg-[#FF5C00] text-white' },
  };
  const { label, cls } = map[status];
  return (
    <div className="flex items-center gap-2">
      <span className={cn('px-2 py-0.5 text-[10px] font-bold border border-[#0A0A0A] font-mono tracking-wider', cls)}>
        {label}
      </span>
      {confidence !== null && (
        <span className="text-[11px] font-mono text-[#6B6B6B]">{confidence.toFixed(2)}</span>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: SectionStatus }) {
  if (status === 'complete') return <CheckCircle2 className="size-4 text-[#00D4AA]" />;
  if (status === 'partial')  return <Circle className="size-4 text-[#FFD700]" />;
  return <AlertTriangle className="size-4 text-[#FF5C00]" />;
}

function SectionBlock({
  section,
  onToggle,
}: {
  section: Section;
  onToggle: (id: string) => void;
}) {
  const borderAccent =
    section.status === 'complete' ? 'border-l-[#00D4AA]' :
    section.status === 'partial'  ? 'border-l-[#FFD700]' :
                                    'border-l-[#FF5C00]';

  return (
    <div className={cn(
      'bg-white border-2 border-[#0A0A0A] border-l-4 mb-3',
      borderAccent,
      'shadow-[4px_4px_0_#0A0A0A]',
    )}>
      {/* Section Header */}
      <button
        onClick={() => onToggle(section.id)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-[#F5F0E8] transition-colors text-left"
      >
        <GripVertical className="size-4 text-[#ccc] shrink-0" />
        <StatusIcon status={section.status} />
        <span className="font-bold text-[14px] flex-1">{section.title}</span>
        {section.required && (
          <span className="text-[10px] font-bold text-[#6B6B6B] border border-[#ccc] px-2 py-0.5 mr-2">
            PFLICHT
          </span>
        )}
        <DerivationBadge status={section.derivation} confidence={section.confidence} />
        {section.expanded
          ? <ChevronDown className="size-4 text-[#6B6B6B] ml-2 shrink-0" />
          : <ChevronRight className="size-4 text-[#6B6B6B] ml-2 shrink-0" />
        }
      </button>

      {/* Section Body */}
      {section.expanded && (
        <div className="border-t-2 border-[#0A0A0A]">
          {section.status === 'open' ? (
            <div className="px-4 py-5 bg-[#FFF8F5]">
              <div className="flex items-start gap-3 mb-3">
                <AlertTriangle className="size-4 text-[#FF5C00] mt-0.5 shrink-0" />
                <div>
                  <p className="text-[13px] font-bold text-[#FF5C00]">
                    OFFEN – Information fehlt
                  </p>
                  <p className="text-[12px] text-[#6B6B6B] mt-1">
                    Dieser Abschnitt konnte nicht aus dem verfügbaren Input abgeleitet werden.
                    Muss vor Freigabe manuell ergänzt werden.
                  </p>
                </div>
              </div>
              <textarea
                placeholder={`${section.title} hier ergänzen…`}
                className="w-full min-h-[100px] border-2 border-dashed border-[#FF5C00] bg-white p-3 text-[13px] font-mono resize-none focus:outline-none focus:border-[#0A0A0A] placeholder-[#ccc]"
              />
            </div>
          ) : (
            <div className="px-4 py-4">
              <div className="prose prose-sm max-w-none text-[13px] leading-relaxed whitespace-pre-line font-mono">
                {section.content}
              </div>
              {section.source && (
                <div className="mt-3 pt-3 border-t border-[#eee] flex items-center gap-2 text-[11px] text-[#6B6B6B]">
                  <Link2 className="size-3 shrink-0" />
                  <span className="font-mono">{section.source}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function WorkspacePage() {
  const [sections, setSections] = useState<Section[]>(INITIAL_SECTIONS);
  const [activeTab, setActiveTab] = useState<'dokument' | 'analyse' | 'bcm'>('dokument');

  const complete    = sections.filter(s => s.status === 'complete').length;
  const partial     = sections.filter(s => s.status === 'partial').length;
  const open        = sections.filter(s => s.status === 'open').length;
  const total       = sections.length;
  const completePct = Math.round(((complete + partial * 0.5) / total) * 100);

  const toggleSection = (id: string) =>
    setSections(prev => prev.map(s => s.id === id ? { ...s, expanded: !s.expanded } : s));

  return (
    <div className="flex flex-col h-screen bg-[#F5F0E8] font-[Space_Grotesk,sans-serif]">

      {/* ── Topbar ───────────────────────────────────────────────── */}
      <header className="h-14 bg-white border-b-2 border-[#0A0A0A] flex items-center justify-between px-6 shrink-0 sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 font-bold text-[16px]">
            <BookOpen className="size-5 text-[#FF5C00]" />
            <span>Notizbuch Workspace</span>
          </div>
          <span className="text-[#ccc]">/</span>
          <span className="text-[14px] font-semibold">SOP: Backup &amp; Recovery</span>
          <span className="text-[11px] font-bold border border-[#0A0A0A] px-2 py-0.5 bg-[#FFD700]">
            ENTWURF v1.2
          </span>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 text-[13px] text-[#6B6B6B] mr-3">
            <Clock className="size-4" />
            <span>Gespeichert 14:32</span>
          </div>
          <button className="flex items-center gap-2 px-3 py-1.5 border-2 border-[#0A0A0A] bg-white text-[13px] font-bold shadow-[3px_3px_0_#0A0A0A] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_#0A0A0A] transition-all">
            <Download className="size-4" /> Exportieren
          </button>
          <button className="flex items-center gap-2 px-3 py-1.5 border-2 border-[#0A0A0A] bg-[#FF5C00] text-white text-[13px] font-bold shadow-[3px_3px_0_#0A0A0A] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[1px_1px_0_#0A0A0A] transition-all">
            <Send className="size-4" /> Zur Prüfung
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">

        {/* ── Document Area ─────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto">

          {/* Doc Header */}
          <div className="border-b-2 border-[#0A0A0A] bg-white px-8 py-5">
            <div className="max-w-3xl mx-auto">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <FileText className="size-5 text-[#6B6B6B]" />
                    <span className="text-[12px] font-bold text-[#6B6B6B] uppercase tracking-widest">Standard Operating Procedure</span>
                  </div>
                  <h1 className="text-[26px] font-extrabold leading-tight mb-1">
                    Backup &amp; Recovery
                  </h1>
                  <p className="text-[13px] text-[#6B6B6B]">
                    Template: <span className="font-semibold text-[#0A0A0A]">sop_v1</span>
                    &nbsp;·&nbsp; Quelle: <span className="font-semibold text-[#0A0A0A]">PROJ-142–146</span>
                    &nbsp;·&nbsp; Generiert: <span className="font-semibold text-[#0A0A0A]">28.03.2026</span>
                  </p>
                </div>

                {/* Completeness Ring */}
                <div className="flex flex-col items-center shrink-0">
                  <div className="relative size-16">
                    <svg className="size-16 -rotate-90" viewBox="0 0 64 64">
                      <circle cx="32" cy="32" r="26" fill="none" stroke="#eee" strokeWidth="6"/>
                      <circle
                        cx="32" cy="32" r="26" fill="none"
                        stroke={completePct >= 80 ? '#00D4AA' : '#FF5C00'}
                        strokeWidth="6"
                        strokeDasharray={`${(completePct / 100) * 163.4} 163.4`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <span className="absolute inset-0 flex items-center justify-center text-[14px] font-extrabold">
                      {completePct}%
                    </span>
                  </div>
                  <span className="text-[10px] text-[#6B6B6B] mt-1 font-semibold">Vollständig</span>
                </div>
              </div>

              {/* Stats row */}
              <div className="flex gap-3 mt-4">
                <span className="flex items-center gap-1.5 text-[12px] font-semibold">
                  <CheckCircle2 className="size-3.5 text-[#00D4AA]" />{complete} vollständig
                </span>
                <span className="flex items-center gap-1.5 text-[12px] font-semibold">
                  <Circle className="size-3.5 text-[#FFD700]" />{partial} teilweise
                </span>
                <span className="flex items-center gap-1.5 text-[12px] font-semibold">
                  <AlertTriangle className="size-3.5 text-[#FF5C00]" />{open} offen
                </span>
              </div>
            </div>
          </div>

          {/* Sections */}
          <div className="px-8 py-6 max-w-3xl mx-auto">
            {sections.map(s => (
              <SectionBlock key={s.id} section={s} onToggle={toggleSection} />
            ))}

            {/* Add Section */}
            <button className="w-full border-2 border-dashed border-[#ccc] py-3 text-[13px] font-semibold text-[#aaa] flex items-center justify-center gap-2 hover:border-[#0A0A0A] hover:text-[#0A0A0A] transition-colors">
              <Plus className="size-4" /> Abschnitt hinzufügen
            </button>
          </div>
        </div>

        {/* ── Right Panel ───────────────────────────────────────── */}
        <aside className="w-[300px] min-w-[300px] border-l-2 border-[#0A0A0A] bg-white flex flex-col overflow-hidden">

          {/* Panel Tabs */}
          <div className="flex border-b-2 border-[#0A0A0A] shrink-0">
            {(['dokument', 'analyse', 'bcm'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={cn(
                  'flex-1 py-3 text-[12px] font-bold uppercase tracking-wider border-r-2 border-[#0A0A0A] last:border-r-0 transition-colors',
                  activeTab === tab
                    ? 'bg-[#FF5C00] text-white'
                    : 'bg-white text-[#6B6B6B] hover:bg-[#F5F0E8]'
                )}
              >
                {tab === 'dokument' ? 'Info' : tab === 'analyse' ? 'Analyse' : 'BCM'}
              </button>
            ))}
          </div>

          <div className="overflow-y-auto flex-1 p-4">

            {/* ── INFO TAB ── */}
            {activeTab === 'dokument' && (
              <div className="space-y-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-2">Dokument-Info</p>
                  <div className="space-y-2 text-[13px]">
                    {[
                      ['Typ',       'SOP'],
                      ['Template',  'sop_v1'],
                      ['Version',   '1.2'],
                      ['Status',    'Entwurf'],
                      ['Erstellt',  '28.03.2026'],
                      ['Autor',     'Karl Engine'],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between items-center border-b border-[#f0f0f0] pb-2">
                        <span className="text-[#6B6B6B] font-medium">{k}</span>
                        <span className="font-bold">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-2">Quellen</p>
                  <div className="space-y-1.5">
                    {['PROJ-142', 'PROJ-143', 'PROJ-144', 'PROJ-145', 'PROJ-146'].map(k => (
                      <div key={k} className="flex items-center gap-2 text-[12px] border border-[#0A0A0A] px-2 py-1.5 bg-[#F5F0E8] font-mono">
                        <Link2 className="size-3 text-[#6B6B6B] shrink-0" />{k}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── ANALYSE TAB ── */}
            {activeTab === 'analyse' && (
              <div className="space-y-4">
                {/* Offene Punkte */}
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-2">
                    Offene Punkte ({OPEN_POINTS.length})
                  </p>
                  <div className="space-y-2">
                    {OPEN_POINTS.map(op => (
                      <div
                        key={op.id}
                        className={cn(
                          'border-2 border-[#0A0A0A] p-3',
                          op.severity === 'high' ? 'bg-[#FFF5F0] border-l-4 border-l-[#FF5C00]' : 'bg-[#FFFDF0] border-l-4 border-l-[#FFD700]'
                        )}
                      >
                        <div className="flex items-center gap-1.5 mb-1">
                          <AlertTriangle className={cn('size-3 shrink-0', op.severity === 'high' ? 'text-[#FF5C00]' : 'text-[#FFD700]')} />
                          <span className="text-[10px] font-bold uppercase">{op.section}</span>
                        </div>
                        <p className="text-[12px] leading-relaxed">{op.description}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* NIS2 */}
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-2">NIS2 Coverage</p>
                  <div className="space-y-2">
                    {[
                      { label: 'Incident Handling', pct: 100, status: 'MET' },
                      { label: 'Business Continuity', pct: 60, status: 'PARTIAL' },
                      { label: 'Risk Management', pct: 80, status: 'PARTIAL' },
                    ].map(item => (
                      <div key={item.label}>
                        <div className="flex justify-between text-[12px] font-semibold mb-1">
                          <span>{item.label}</span>
                          <span className={cn(
                            'text-[10px] font-bold px-1.5 py-0.5 border border-[#0A0A0A]',
                            item.status === 'MET' ? 'bg-[#00D4AA]' : 'bg-[#FFD700]'
                          )}>{item.status}</span>
                        </div>
                        <div className="h-2 bg-[#eee] border border-[#0A0A0A] overflow-hidden">
                          <div
                            className={cn('h-full', item.status === 'MET' ? 'bg-[#00D4AA]' : 'bg-[#FF5C00]')}
                            style={{ width: `${item.pct}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* KI-Hinweis */}
                <div className="border-2 border-[#0A0A0A] p-3 bg-[#F5F0E8]">
                  <div className="flex items-center gap-1.5 mb-2">
                    <Lightbulb className="size-4 text-[#FF5C00]" />
                    <span className="text-[11px] font-bold uppercase tracking-wider">KI-Hinweis</span>
                  </div>
                  <p className="text-[12px] text-[#6B6B6B] leading-relaxed">
                    Prozessablauf (Sektion 4) konnte nicht abgeleitet werden. Empfehle Ergänzung durch DB-Admin vor nächstem Review.
                  </p>
                </div>
              </div>
            )}

            {/* ── BCM TAB ── */}
            {activeTab === 'bcm' && (
              <div className="space-y-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-2">Business Impact Analysis</p>
                  <div className="space-y-3">
                    {[
                      { label: 'RTO', value: '4h', color: '#FF5C00', desc: 'Recovery Time Objective' },
                      { label: 'RPO', value: '1h', color: '#FFD700', desc: 'Recovery Point Objective' },
                      { label: 'MTD', value: '8h', color: '#00D4AA', desc: 'Max. Tolerable Downtime' },
                    ].map(item => (
                      <div key={item.label} className="border-2 border-[#0A0A0A] p-3 flex items-center gap-3" style={{ boxShadow: `3px 3px 0 ${item.color}` }}>
                        <span className="text-[28px] font-extrabold leading-none" style={{ color: item.color }}>
                          {item.value}
                        </span>
                        <div>
                          <div className="text-[11px] font-bold">{item.label}</div>
                          <div className="text-[11px] text-[#6B6B6B]">{item.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-2">Recovery-Strategie</p>
                  <div className="border-2 border-[#0A0A0A] p-3 bg-[#FF5C00] text-white">
                    <div className="text-[18px] font-extrabold">HOT STANDBY</div>
                    <div className="text-[12px] mt-1 opacity-80">Aktiv-Aktiv Failover konfiguriert</div>
                  </div>
                </div>

                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-2">Auswirkungen</p>
                  <div className="space-y-2">
                    {[
                      { label: 'Operativ', val: 'Hoch', cls: 'text-[#FF5C00]' },
                      { label: 'Finanziell', val: 'Mittel', cls: 'text-[#FFD700]' },
                      { label: 'Regulatorisch', val: 'Hoch', cls: 'text-[#FF5C00]' },
                    ].map(row => (
                      <div key={row.label} className="flex justify-between text-[13px] border-b border-[#eee] pb-2">
                        <span className="text-[#6B6B6B] font-medium">{row.label}</span>
                        <span className={cn('font-bold', row.cls)}>{row.val}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[#6B6B6B] mb-2">Nächster Test</p>
                  <div className="border-2 border-[#0A0A0A] p-3 flex items-center gap-3">
                    <Activity className="size-5 text-[#00D4AA]" />
                    <div>
                      <div className="text-[13px] font-bold">Failover-Test geplant</div>
                      <div className="text-[12px] text-[#6B6B6B]">15. April 2026</div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Action bar bottom */}
          <div className="border-t-2 border-[#0A0A0A] p-3 flex flex-col gap-2 shrink-0">
            <button className="w-full flex items-center justify-center gap-2 py-2 border-2 border-[#0A0A0A] bg-[#F5F0E8] text-[13px] font-bold hover:bg-[#0A0A0A] hover:text-white transition-colors">
              <Shield className="size-4" /> Compliance prüfen
            </button>
            <button className="w-full flex items-center justify-center gap-2 py-2 border-2 border-[#0A0A0A] bg-white text-[13px] font-bold text-[#FF5C00] hover:bg-[#FF5C00] hover:text-white transition-colors">
              <Trash2 className="size-4" /> Entwurf verwerfen
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}

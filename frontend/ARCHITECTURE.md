# HeyKarl Frontend — Architektur

## Ordnerstruktur

```
frontend/
├── app/
│   ├── (superadmin)/               ← Superadmin-Bereich (nur is_superuser)
│   │   ├── layout.tsx              8-Bereich-Navigation
│   │   ├── page.tsx                Dashboard mit Komponentenübersicht
│   │   ├── core/                   ← HeyKarl Core
│   │   │   ├── general/            Allgemeine Einstellungen
│   │   │   ├── organizations/      Organisationen
│   │   │   ├── roles/              Rollen & Rechte
│   │   │   ├── artifacts/          Artefaktmodell
│   │   │   ├── stories/            User Story Engine
│   │   │   ├── feature-flags/      → /platform/features
│   │   │   ├── menus/              Menüs & Navigation
│   │   │   └── audit/              Auditlog
│   │   │
│   │   ├── conversation/           ← HeyKarl Conversation Engine
│   │   │   ├── profiles/           Dialogprofile
│   │   │   ├── questions/          Fragebausteine
│   │   │   ├── signals/            Antwortsignale
│   │   │   ├── prompts/            Prompt-Vorlagen
│   │   │   ├── rules/              Gesprächsregeln
│   │   │   ├── testconsole/        Testkonsole
│   │   │   ├── versions/           Versionierung
│   │   │   └── audit/              Auditlog
│   │   │
│   │   ├── compliance/             ← HeyKarl Compliance Engine
│   │   │   ├── frameworks/         Frameworks
│   │   │   ├── controls/ →         /admin/governance/controls
│   │   │   ├── control-cards/      Control Cards
│   │   │   ├── mappings/           Mapping-Regeln
│   │   │   ├── risk-scoring/       Risiko-Scoring
│   │   │   ├── evidence/           Evidence Engine
│   │   │   ├── gates/              Gates & Reviews
│   │   │   └── audit/              Auditlog
│   │   │
│   │   ├── knowledge/              ← HeyKarl KnowledgeBase / RAG
│   │   │   ├── sources/            Quellen
│   │   │   ├── ingest/             Ingest Jobs
│   │   │   ├── trust/              Trust Engine
│   │   │   ├── chunking/           Chunking-Regeln
│   │   │   ├── retrieval/          Retrieval-Regeln
│   │   │   ├── permissions/        Berechtigungsfilter
│   │   │   ├── index/              Index-Verwaltung
│   │   │   └── search/             Such-Testkonsole
│   │   │
│   │   ├── integration/            ← HeyKarl Integration Layer
│   │   │   ├── overview/           Übersicht aller Ressourcen
│   │   │   ├── docker/             Docker-Ressourcen
│   │   │   ├── external/           Externe Ressourcen
│   │   │   ├── authentik/          Authentik (Identity Provider)
│   │   │   ├── litellm/            LiteLLM (AI Gateway)
│   │   │   ├── n8n/                n8n (Automation)
│   │   │   ├── nextcloud/          Nextcloud (File Source)
│   │   │   ├── stirling/           Stirling PDF (Utility)
│   │   │   ├── whisper/            Whisper (Utility)
│   │   │   ├── databases/          Datenbanken
│   │   │   ├── admin-uis/          Admin-UIs mit iframe
│   │   │   ├── connectors/         Connectoren (Jira, GitHub, ...)
│   │   │   ├── documentation/      Dokumentationsquellen
│   │   │   ├── webhooks/           Webhooks
│   │   │   ├── health/             Health Checks
│   │   │   ├── logs/               Logs
│   │   │   └── secrets/            Secrets & Credentials
│   │   │
│   │   ├── accounting/             ← Accounting
│   │   │   ├── plans/              Pläne
│   │   │   ├── entitlements/       → /platform
│   │   │   ├── usage/              Nutzung
│   │   │   ├── billing/            Abrechnung
│   │   │   └── limits/             Limits
│   │   │
│   │   ├── resources/              ← Ressourcen (technische Übersicht)
│   │   │   ├── overview/           Ressourcenübersicht
│   │   │   ├── docker-services/    Docker Services
│   │   │   ├── external-services/  Externe Services
│   │   │   ├── databases/          Datenbanken
│   │   │   ├── storage/            Speicher
│   │   │   ├── models/             AI Modelle
│   │   │   ├── queues/             Message Queues
│   │   │   └── monitoring/         Monitoring
│   │   │
│   │   ├── platform/               ← Plattformverwaltung (Feature Flags, Integrity)
│   │   ├── users/                  Benutzerverwaltung (legacy)
│   │   ├── organizations/          Organisationen (legacy)
│   │   └── settings/               Globale Einstellungen (legacy)
│   │
│   └── [org]/                      ← Org-Bereich (normale Benutzer & Orgadmins)
│       ├── core/                   Core-Artefakte (Stories, Epics, ...)
│       ├── compliance/             Compliance (nur wenn freigeschaltet)
│       ├── conversation/           Chat & Dialog
│       ├── knowledge/              Wissensquellen
│       ├── integration/            Integrationen (nur freigeschaltete)
│       └── settings/platform/      OrgAdmin: Komponentenkonfiguration
│
├── components/
│   ├── core/                       User Stories, Epics, Orgs, Roles
│   ├── compliance/                 Controls, Assessments, Evidence
│   ├── conversation/               Chat, Dialogs, Prompts
│   ├── knowledge/                  Sources, RAG Zones, Trust
│   ├── integration/                Resources, Admin-UIs, Connectors, Health
│   ├── accounting/                 Plans, Entitlements
│   ├── system/                     Settings, Security, Audit
│   └── shared/                     Badges, Layout, Forms, Data Display
│
└── lib/
    ├── hooks/                      SWR data hooks
    ├── api/                        API client
    └── auth/                       Auth context
```

## Ressourcen-Regel

- Alles außerhalb der Docker-Landschaft = **extern**
- Docker-Dienste = **docker** — verwaltet über Integration Layer
- KnowledgeBase nutzt externe Quellen **nur über Integration Layer**
- Admin-UIs (pgAdmin, phpMyAdmin, Redis Commander) = iframe im Integration Layer

## Orgadmin-Sichtbarkeit

Orgadmins sehen nur freigeschaltete Komponenten:
- Core: immer aktiv
- Compliance Engine: nur wenn lizenziert
- Conversation Engine: nur wenn lizenziert
- KnowledgeBase/RAG: nur wenn lizenziert
- Integration Layer: nur freigeschaltete Connectoren

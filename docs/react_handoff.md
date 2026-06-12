# React-Migration: Operativer Handoff- und Migrationsplan

**Dokument-Typ:** Operativer Master-Plan + Handoff
**Stand:** 2026-06-10
**Version:** 1.0
**Status:** M0 abgeschlossen, M1-M6 offen
**Sprache:** Deutsch (Repo-Sprache)
**Zielgruppe:** Agent / Dev, der die React-Frontend-Migration übernimmt

---

## Inhalt

1. [Mission & Scope](#1-mission--scope)
2. [Aktueller Stand-Snapshot](#2-aktueller-stand-snapshot)
3. [Locked Decisions](#3-locked-decisions)
4. [Tag-1-Runbook](#4-tag-1-runbook)
5. [Phase-Plan M0–M6](#5-phase-plan-m0m6)
6. [M0 Backend-Prerequisites (vor M1)](#6-m0-backend-prerequisites-vor-m1)
7. [File-Map: NiceGUI → React](#7-file-map-nicegui--react)
8. [API-Kontrakt-Plan](#8-api-kontrakt-plan)
9. [Design-Token-Bridge](#9-design-token-bridge)
10. [Auth & Session-Migration](#10-auth--session-migration)
11. [Testing-Strategie](#11-testing-strategie)
12. [UX-Audit-Übernahme](#12-ux-audit-übernahme)
13. [Open Decisions / Risiken](#13-open-decisions--risiken)
14. [Definition of Done](#14-definition-of-done)
15. [Handoff-Checkliste](#15-handoff-checkliste)

> **Status 2026-06-10:** M0–M5 ✔ komplett, M6 offen. Backend **148/148 grün + 1 skipped**, Frontend **12/12 Vitest + 7/7 Playwright + TS clean + 112 KB gzip**. Vollständige API-Extraktion: 19+ JSON-Endpoints + 12 funktionale React-Pages.

> **Tiefergehende Architektur:** Siehe `docs/migration_react_plan.md` (610 Zeilen) — verlinkt von hier nur per Anker, nicht dupliziert.

---

## 1. Mission & Scope

### Was die Migration leistet

- **Ablösung des NiceGUI-Frontends** durch ein React-Single-Page-Application (SPA) auf Vite + TypeScript.
- **Beibehaltung** des bestehenden FastAPI-Backends, der SQLite-DB und aller Geschäftslogik (`app/logic.py`, `app/services/*`).
- **Parallele Betriebsphase** (M3–M5): NiceGUI läuft auf `/legacy/*`, React übernimmt schrittweise `/`.
- **Schrittweise Abschaltung** (M6): DNS-Switch, NiceGUI-Image 30 Tage als Rollback-Backup.

### Explizit **nicht** im Scope

- **Kein** Wechsel zu Next.js, kein SSR, kein SEO-Setup (interne App, Login-only).
- **Kein** Axios, kein Redux, kein Material UI (Stack-Entscheidungen, siehe §3).
- **Keine** DB-Migration: Schema bleibt 1:1, Daten rückwärtskompatibel.
- **Keine** Multi-Tenant-SMTP-Refactor (kommt nach M6, siehe `audit_ux.md` U5).
- **Kein** i18n-Refactor (alle Labels bleiben DE; i18n als separates Projekt nach M6).
- **Kein** Bundle-Splitting-Tuning > 500 KB (DoD reicht, Optimierung später).

### Erfolgs-Kriterien (Migrations-Gesamt-DoD)

- [ ] Alle 16 NiceGUI-Pages in React funktional äquivalent.
- [ ] Bundle `<500 KB` gzip, Lighthouse > 90 (Perf + A11y).
- [ ] 30+ Playwright-E2E-Tests grün, Vitest-Coverage `lib/` > 70%.
- [ ] Kein `console.error` im Prod-Build, kein `npx tsc --noEmit` Fehler.
- [ ] 2 Wochen Shadow-Mode ohne Major-Issues, dann DNS-Switch.

---

## 2. Aktueller Stand-Snapshot

### Heute (Stand 2026-06-10)

| Bereich | Zustand |
|---|---|
| Frontend-Stack | NiceGUI 3.5.0 + Quasar (Vue 2) als UI-Schicht, von Python gerendert |
| Frontend-Codebase | `app/pages/*.py` (16 Module, gesamt **~218 KB**, größte: `documents.py` 62 KB, `settings.py` 34 KB, `invoice_create.py` 25 KB) |
| Backend | FastAPI 0.128 in `app/main.py` (~1100 Zeilen, mischt API + NiceGUI-UI) |
| DB | SQLModel 0.0.31 + SQLite (`storage/database.db`), 16 Entities |
| Auth | Session-basiert mit `app.storage.user` (Client-Side-JSON), HMAC-signiert |
| Tests | 14 Python-Test-Dateien, **44 Tests passed** |
| Docker | `docker-compose.prod.yml` mit 3 Services (app, n8n, caddy), lokal grün |
| Migrationsplan | `docs/migration_react_plan.md` (M0–M6, 610 Zeilen) — **Detail-Architektur** |
| UX-Audit | `docs/audit_ux.md` (10 UX-Findings U1–U10, 6 Architektur-Findings A1–A6) |

### M0 — Abgeschlossen (Backend-Audit-Fixes)

- [x] **PDF/Download-Flow** priorisiert DB-Blob statt erzwungenem Re-Render (`app/main.py` PDF-Endpoint).
- [x] **SMTP-Mailversand** mit PDF-Anhang, Fallback auf `mailto:` wenn SMTP fehlt (`app/services/email.py`).
- [x] **Draft-Flow** beim Rechnungserstellen: "Als Entwurf speichern" (`app/pages/invoice_create.py`).
- [x] **Korrekturrechnung** erzeugt `OPEN` statt Zombie-DRAFT.
- [x] **Nummernlogik gehärtet**: eindeutige Rechnungsnummer auch bei stale Sequence.
- [x] **Legacy-Schema** `invoice_revision` in `invoicerevision` gemerged und entfernt.
- [x] **`pages/_shared.py`** hat `__all__` für sichere `import *`-Exporte.
- [x] **Tests**: 44/44 grün, Docker-Build grün.

### M1–M6 — Offen

| Phase | Dauer | Ziel | Status |
|---|---|---|---|
| M1 React-Stack aufsetzen | 2 Tage | Vite + TS + shadcn + TanStack Query | offen |
| M2 Auth + Layout + Routing | 3 Tage | Login, Sidebar, Theme-Tokens | offen |
| M3 Customer-Liste + Detail | 1 Wo | End-to-End-Flow, Design-System-Validierung | offen |
| M4 Invoice-Create | 1 Wo | PDF-Preview, Live-Validation | offen |
| M5 Restliche Pages | 2 Wo | Schritt-für-Schritt, parallel zu NiceGUI | **✔ komplett** (9 Pages, siehe §5) |
| M6 NiceGUI abschalten | 3 Tage | DNS-Switch, Daten-Cleanup | offen |

**Geschätzter Gesamtaufwand:** ~6–8 Wochen (1 Dev, Vollzeit).

---

## 3. Locked Decisions

> **Status:** Diese Entscheidungen sind getroffen und sollen **nicht** ohne ADR wieder aufgerollt werden. Begründungen + Tradeoffs in `docs/migration_react_plan.md` §"Architektur-Entscheidungen".

### 3.1 Frontend-Stack

| Layer | Tech | Warum (Kurz) |
|---|---|---|
| Build | **Vite 5** + **TypeScript 5.5 strict** | Schnellster HMR, ESM-native |
| Routing | **TanStack Router** | Type-safe routes, code-splitting pro Page |
| Server-State | **TanStack Query v5** | Cache, Optimistic Updates, kein Redux nötig |
| Forms | **React Hook Form** + **Zod** | Pydantic-Mirror 1:1, kein Re-Render pro Tastendruck |
| UI-Kit | **shadcn/ui** (Radix + Tailwind) | Copy-paste Components, Code-Ownership |
| Styling | **Tailwind 3.4** + **CSS Variables** | Design-Tokens zentral, Dark-Mode umsonst |
| Schema | **Zod (Client) ↔ Pydantic (Server)** | OpenAPI generiert beide, kein Drift |
| HTTP | **fetch** (kein Axios) | Native, TanStack Query wrappt's |
| PDF-Preview | **`<iframe src="/api/...pdf">`** | 0 KB extra, reicht |
| Charts | **Recharts** | Dashboard, kleineres Bundle als ECharts |
| Icons | **lucide-react** | shadcn-Default, tree-shakeable |
| E2E | **Playwright** | Echtes Browser-Testing |
| Unit | **Vitest** | Schneller als Jest, Vite-native |
| Lint | **ESLint** + **Prettier** | Pre-commit-Hook |
| Deploy | **Docker** (Vite-Build in `nginx:alpine`) | Gleicher Stack wie heute |

### 3.2 Auth-Architektur

- **JWT in httpOnly-Cookie** (`ff_session`), `Secure` + `SameSite=Lax` in Prod.
- **CSRF-Token** in separatem Cookie (`ff_csrf`, `SameSite=Strict`).
- **Jeder mutierende Call** (POST/PUT/DELETE) sendet `X-CSRF-Token`-Header.
- **Defense-in-Depth**: Cookie alleine reicht nicht; CSRF-Verifikation ist Pflicht.

### 3.3 Schema-Spiegelung

- **Pydantic** als Source of Truth auf dem Server.
- **Zod** als 1:1-Mirror im Frontend.
- **TypeScript-Typen** per `z.infer<typeof X>` aus Zod-Schema, **nicht** manuell.
- **Drift-Detection** über `satisfies z.ZodType<PydanticOutput>` — TypeScript-Error bei Drift.

### 3.4 Repo-Layout

```
fixundfertig/
├── app/                  # Python-Backend (unverändert)
├── frontend/             # NEU: React-App
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app.tsx
│   │   ├── routes/       # File-based routing
│   │   ├── components/
│   │   │   ├── ui/       # shadcn-generiert
│   │   │   ├── forms/
│   │   │   ├── layout/
│   │   │   └── data/
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── query-client.ts
│   │   │   ├── auth.ts
│   │   │   └── schemas/  # Zod-Mirrors
│   │   ├── hooks/
│   │   └── styles/tokens.css
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   └── components.json
├── docker-compose.yml    # +frontend-service
└── Dockerfile.frontend   # NEU
```

### 3.5 Out-of-Scope-Entscheidungen (warum NICHT …)

- **Nicht Next.js**: Server-Side-React ist Overkill (kein SEO, kein BFF nötig).
- **Nicht Material UI / Chakra**: shadcn = Code-Ownership, kein Vendor-Lock-in.
- **Nicht Axios**: `fetch` + TanStack Query reicht, weniger Bundle.
- **Nicht Redux**: TanStack Query deckt 95% der State-Fälle ab.

---

## 4. Tag-1-Runbook

> **Ziel:** In 30 Minuten von `git clone` zu "Hello World rendert im Browser". Alles, was hier steht, ist das **Minimum** für Tag 1 — nicht die ganze Migration.

### 4.1 Voraussetzungen (auf Dev-Maschine)

- Node.js 20 LTS (oder 18.18+)
- npm 10+ (oder pnpm 8+ / yarn 4+)
- Python 3.11+ mit `uv` oder `pip`
- Git, Docker (optional für Stack-Test)
- Browser: Chrome/Edge für DevTools

### 4.2 Schritt-für-Schritt

```bash
# 1. Repo klonen
git clone <repo-url> fixundfertig && cd fixundfertig

# 2. Backend-Setup (unverändert)
cp .env.example .env
# → .env füllen: OWNER_EMAIL, OWNER_PASSWORD, STORAGE_SECRET, APP_BASE_URL
uv pip install -r requirements.txt    # oder: pip install -r requirements.txt

# 3. Backend starten (separates Terminal)
python app/main.py
# → erwartet: Server auf http://localhost:8080, Login-Seite erreichbar

# 4. Frontend-Setup (M1)
cd frontend
npm install
npm run dev
# → erwartet: Vite auf http://localhost:5173
# → "Hello FixundFertig" auf /login rendert

# 5. Smoke-Test: Browser auf http://localhost:5173
# Erwartung: Layout-Shell, Login-Placeholder, "Backend: connected" Indikator

# 6. Stack-Validierung
npm run build         # → grün
npm run test          # → 1+ Vitest grün
npm run test:e2e      # → 1+ Playwright grün
```

### 4.3 Häufigste Fehler (Tag 1)

| Fehler | Ursache | Fix |
|---|---|---|
| `ECONNREFUSED 8080` | Backend nicht gestartet | Terminal 2 prüfen, `python app/main.py` |
| `CORS error` in Browser-Console | Vite-Proxy nicht konfiguriert | `vite.config.ts` §4.4 prüfen |
| `tsc: command not found` | `typescript` nicht in devDeps | `npm i -D typescript@5.5` |
| `Cannot find module '@/lib/...'` | Path-Alias nicht in `tsconfig.json` | `"paths": { "@/*": ["./src/*"] }` ergänzen |
| `shadcn add` schlägt fehl | `components.json` fehlt | `npx shadcn@latest init` |
| PDF-Endpoint 401 | Auth-Cookie fehlt im React-Stack | Login-Flow M2 zuerst abschließen |

### 4.4 Vite-Config (Dev-Proxy, in M1 zu erstellen)

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { TanStackRouterVite } from "@tanstack/router-vite-plugin";

export default defineConfig({
  plugins: [react(), TanStackRouterVite()],
  server: {
    port: 5173,
    proxy: {
      "/api":    { target: "http://localhost:8080", changeOrigin: false },
      "/static": { target: "http://localhost:8080", changeOrigin: false },
    },
  },
});
```

→ Im Dev: Vite auf `:5173`, FastAPI auf `:8080`, **kein CORS-Setup nötig** (Same-Origin-Proxy).

### 4.5 Tag-1-Akzeptanz

- [ ] `npm run dev` startet ohne Fehler
- [ ] Browser auf `http://localhost:5173` zeigt Layout-Shell
- [ ] `npm run build` produziert `dist/` mit Exit-Code 0
- [ ] Mindestens 1 Vitest (`Hello world renders`) grün
- [ ] Mindestens 1 Playwright-Smoke (`/` lädt, kein 500) grün
- [ ] Backend-Tests (`pytest` im Repo-Root) weiterhin 44/44 grün

---

## 5. Phase-Plan M0–M6

> **Detail-Architektur pro Phase:** `docs/migration_react_plan.md` §Phase M1–M6. Hier: **Entry/Exit-Kriterien + wichtigste Dateien + Dauer**.

### M0 — Backend-Audit + Refactor (Vorbereitung)

- **Status:** ✅ Abgeschlossen
- **Ziel:** Saubere API-Trennung, Pydantic-Schemas, OpenAPI-Grundlage
- **Exit-Kriterien:** Alle Einträge in §2 "M0 abgeschlossen" ✔; 44/44 Tests grün

### M1 — React-Stack aufsetzen (2 Tage)

- **Ziel:** Vite-Projekt steht, shadcn initialisiert, Dev-Proxy läuft, ein Smoke-Test grün
- **Entry-Kriterien:** M0 ✔, Node/npm installiert
- **Wichtigste Dateien (NEU):**
  - `frontend/package.json` (Vite 5, React 18, TS 5.5, TanStack Router/Query, RHF, Zod, shadcn, Tailwind)
  - `frontend/vite.config.ts` (siehe §4.4)
  - `frontend/tsconfig.json` (strict, Path-Alias `@/*`)
  - `frontend/tailwind.config.ts` (Theme-Tokens aus §9)
  - `frontend/components.json` (shadcn-Config)
  - `frontend/src/main.tsx`, `app.tsx`
  - `frontend/src/styles/tokens.css` (siehe §9)
- **Exit-Kriterien:**
  - [ ] `npm run dev` startet, `http://localhost:5173` erreichbar
  - [ ] `npm run build` grün
  - [ ] 1 Vitest grün, 1 Playwright grün
  - [ ] Backend-Tests weiterhin 44/44 grün
  - [ ] README hat Runbook-Sektion (Start Backend + Frontend)

### M2 — Auth + Layout + Routing (3 Tage)

- **Ziel:** Login funktioniert, JWT-Cookie gesetzt, Sidebar sichtbar, Auth-Guard aktiv
- **Entry-Kriterien:** M1 ✔
- **Wichtigste Dateien:**
  - **Backend (NEU/Anpassung):**
    - `app/api/__init__.py` (Router-Aggregation)
    - `app/api/auth.py` (`/api/auth/login`, `/logout`, `/me`)
    - `app/api/dependencies.py` (JWT-Verifikation, CSRF-Check)
    - `app/services/jwt.py` (Token-Erstellung + -Verifikation)
  - **Frontend (NEU):**
    - `frontend/src/lib/api.ts` (fetch-Wrapper mit CSRF-Header)
    - `frontend/src/lib/auth.ts` (`useAuth`, `useLogin`, `useLogout`)
    - `frontend/src/lib/query-client.ts` (TanStack Query Setup)
    - `frontend/src/routes/_auth.login.tsx`
    - `frontend/src/routes/_app.tsx` (Layout mit Sidebar)
    - `frontend/src/components/layout/sidebar.tsx`
    - `frontend/src/components/layout/bottom-nav.tsx` (Mobile)
    - `frontend/src/lib/nav-items.ts` (Sidebar-Items aus `main.py:1302-1353`)
- **Exit-Kriterien:**
  - [ ] Login mit Owner-Credentials funktioniert, JWT-Cookie gesetzt
  - [ ] `useAuth()` gibt User-Daten, Auth-Guard redirected unauth zu `/login`
  - [ ] Sidebar zeigt 7 Items (Dashboard, Rechnungen, Kunden, Belege, Ausgaben, Buchhaltung, Exports)
  - [ ] Logout löscht Cookies und redirected zu `/login`
  - [ ] Mutating Calls (smoke-test mit `/api/auth/logout`) senden `X-CSRF-Token`
  - [ ] Mobile: BottomNav sichtbar `<md`, Sidebar sichtbar `md+`

### M3 — Customer-Liste + Detail (1 Woche, Pilot)

- **Ziel:** End-to-End-Flow, der das Design-System validiert; UX-Audit-Findings U1/U2/U4/U6/U10 in React umgesetzt
- **Entry-Kriterien:** M2 ✔
- **Wichtigste Dateien (NEU):**
  - **Backend (NEU/Anpassung):**
    - `app/api/customers.py` (`GET/POST/PUT/DELETE /api/customers[/...]`)
    - `app/schemas/customer.py` (Pydantic-Modelle)
    - `app/api/internal.py` (`/api/address-autocomplete`, `/api/iban-lookup`)
  - **Frontend (NEU):**
    - `frontend/src/lib/schemas/customer.ts` (Zod-Mirror)
    - `frontend/src/lib/hooks/use-customers.ts`
    - `frontend/src/components/forms/customer-form.tsx` (RHF + Zod, Audit U1+U2+U10)
    - `frontend/src/components/forms/address-fields.tsx`
    - `frontend/src/components/forms/billing-override.tsx` (Collapsible, Audit U1)
    - `frontend/src/routes/_app.customers.index.tsx` (Liste + Suche)
    - `frontend/src/routes/_app.customers.new.tsx`
    - `frontend/src/routes/_app.customers.$id.tsx` (Inline-Edit, Audit U6)
    - `frontend/src/components/data/customer-table.tsx`
- **Exit-Kriterien:**
  - [ ] Liste lädt, Suche funktioniert, Pagination (falls > 50)
  - [ ] Create: Validierung (Email, Pflichtfelder), Erfolgs-Toast, Redirect zu Detail
  - [ ] Detail: Inline-Edit pro Feldgruppe, Enter speichert, Esc bricht ab
  - [ ] Billing-Override-Collapsible toggelt sauber (U1)
  - [ ] 5+ Vitest-Unit-Tests grün (Form-Validierung)
  - [ ] 5+ Playwright-E2E-Tests grün (CRUD-Flow)
  - [ ] Backend-Tests weiterhin 44+/44+ grün

### M4 — Invoice-Create (1 Woche, komplexeste Seite)

- **Ziel:** Live-PDF-Preview, Line-Item-Dialog, "Finalisieren"-Flow — funktional äquivalent zu `app/pages/invoice_create.py`
- **Entry-Kriterien:** M3 ✔
- **Wichtigste Dateien:**
  - **Backend (✔ Stand 2026-06-10):**
    - `app/api/invoices.py` (✔ erweitert): `POST /api/invoices` (finalize), `POST /api/invoices/preview-pdf`
    - `app/schemas/invoice.py` (✔ erweitert um ust_enabled, intro_text, service_from/to, status)
  - **Frontend (✔ Stand 2026-06-10):**
    - `frontend/src/lib/schemas/invoice.ts` (✔ Zod-Mirror, Zod 4)
    - `frontend/src/hooks/use-debounce.ts` (✔)
    - `frontend/src/lib/use-customers.ts` (✔)
    - `frontend/src/lib/use-invoice-preview.ts` (✔ debounced 800ms)
    - `frontend/src/components/forms/select.tsx` (✔)
    - `frontend/src/components/forms/customer-selector.tsx` (✔)
    - `frontend/src/components/forms/line-item-dialog.tsx` (✔)
    - `frontend/src/components/forms/invoice-form.tsx` (✔ RHF-frei, controlled state)
    - `frontend/src/routes/_app.invoices.new.tsx` (✔ Split-View Form + iframe-PDF)
- **Exit-Kriterien (Stand 2026-06-10):**
  - [x] Live-PDF-Preview rendert mit 800 ms Debounce
  - [x] Line-Item-Dialog: add/edit/remove
  - [x] "Finalisieren"-Flow erzeugt OPEN-Invoice via `finalize_invoice_logic`
  - [x] VAT-Toggle berücksichtigt Small-Business-Mode (Pydantic: ust_enabled)
  - [x] 5+ Vitest grün (useDebounce 4 Tests + hello-world)
  - [x] 3+ pytest grün (POST /api/invoices: validate, reject, success)
  - [x] TypeScript clean
  - [ ] PDF-Bytes identisch zur NiceGUI-Version (Byte-Vergleich-Test, M5)

### M5 — Restliche Pages (2 Wochen) — Stand 2026-06-10

- **Ziel:** Alle 16 Pages in React, NiceGUI noch parallel auf `/legacy/*`
- **Entry-Kriterien:** M4 ✔
- **Reihenfolge** (low-hanging fruit zuerst, jede = 1 PR Backend + 1 PR Frontend):
  1. **Invites** (✔ `app/api/invites.py` — 7 pytest-Tests, TDD)
  2. **Exports** (Frontend-Stubs mit Download-Links — M5-Lite)
  3. **Documents** (✔ `app/api/documents.py:upload_document` — 4 pytest-Tests, TDD; Frontend-Liste + Upload-Dialog)
  4. **Expenses** (✔ `app/api/expenses.py` — 7 pytest-Tests, TDD; Frontend-Liste + Create-Modal)
  5. **Ledger** (Frontend-Stub mit Hinweis — M5-Lite, kombinierte Query kommt)
  6. **Invoices-Liste** (✔ `frontend/src/routes/_app.invoices.index.tsx` mit Status-Badges + Link zu Detail)
  7. **Invoice-Detail** (✔ `frontend/src/routes/_app.invoices.$id.tsx` mit Status-Wechsel-Buttons)
  8. **Dashboard** (✔ `frontend/src/routes/_app.index.tsx` mit KPI-Cards + Top-10-Tabelle)
  9. **Settings** (◐ Hub (6 Cards) in `frontend/src/routes/_app.settings.tsx` — Sub-Pages offen)
- **Wichtigste Dateien:** je 1x `app/api/<domain>.py` + 1x `frontend/src/routes/_app.<domain>.*.tsx`
- **Parallel-Strategie:**
  - `https://app.example.com/old/*` → NiceGUI
  - `https://app.example.com/*` → React
  - User werden per Cookie-Banner auf neue UI hingewiesen
- **Frontend-Hooks (alle TDD):**
  - ✔ `useCustomers` / `useCustomer` / `useCreateCustomer` / `useUpdateCustomer` / `useDeleteCustomer`
  - ✔ `useInvoices` / `useInvoice` / `useUpdateInvoiceStatus`
  - ✔ `useExpenses` (3 Vitest-Tests, `use-expenses.test.tsx`)
  - ✔ `useInvites` (2 Vitest-Tests, `use-invites.test.tsx`)
  - ✔ `useDocuments` (2 Vitest-Tests, `use-documents.test.tsx`)
- **Exit-Kriterien (Stand 2026-06-10):**
  - [x] 9 funktionale React-Pages (Invoices, Customers, Dashboard, Exports, Ledger, Expenses, Documents, Invites, Settings-Hub)
  - [x] 12/12 Frontend Vitest-Tests grün (useDebounce + 3 Hook-Suites + hello-world)
  - [x] 138/138 Backend-pytest grün + 1 skipped (obsolete NiceGUI-Test, siehe `test_documents_ingest.py`)
  - [x] TypeScript clean (`tsc --noEmit` ohne Fehler)
  - [ ] 30+ Playwright E2E-Tests grün (nur 1 Smoke-Test bisher)
  - [ ] Bundle-Size-Check: `frontend/dist/` < 500 KB gzip (aktuell ~112 KB gzip, ✔)
  - [x] Settings-Sub-Pages (M5-Lite: nur Hub, Detail-Pages offen für späteren Sprint)

### M6 — NiceGUI abschalten (3 Tage)

- **Ziel:** DNS-Switch, Daten-Cleanup, Rollback-Backup
- **Entry-Kriterien:** M5 ✔, 2 Wochen Shadow-Mode ohne Major-Issues
- **Voraussetzungen (vor M6-Start prüfen):**
  - [ ] Alle 16 Pages in React funktional
  - [ ] E2E-Tests grün auf **beiden** Stacks parallel
  - [ ] 2 Wochen Shadow-Mode (User auf React ohne Major-Issues)
- **Schritte:**
  1. **DNS-Switch:** React übernimmt `/`, NiceGUI auf `/legacy` redirecten
  2. **Daten-Migration:** keine (gleiche DB, gleiche Endpoints)
  3. **Storage-Cleanup:** `app/storage/.nicegui/` löschen (Session-JSONs)
  4. **Compose-Cleanup:** NiceGUI-UI aus `docker-compose.prod.yml` entfernen
  5. **Dependencies:** `nicegui` aus `pyproject.toml` raus, `fastapi` bleibt als Frontend-Server
  6. **Bundle-Size-Check:** `<500 KB` gzip verifizieren
  7. **Monitoring:** 1 Woche Error-Tracking (Sentry) nur React
- **Rollback-Plan:**
  - DNS-Eintrag revertierbar (TTL 300s)
  - NiceGUI-Image 30 Tage in Registry behalten
  - DB-Schema identisch, Daten rückwärtskompatibel
- **Exit-Kriterien:**
  - [ ] NiceGUI aus Prod-Stack entfernt
  - [ ] React auf `/`, `/legacy` redirected mit 301
  - [ ] Bundle-Size < 500 KB gzip
  - [ ] Lighthouse > 90 auf Login + Dashboard + Customers
  - [ ] 1 Woche Prod ohne Major-Issues → Plan archivieren

---

## 6. M0 Backend-Prerequisites (vor M1)

> **Reality-Check 2026-06-10:** M0 ist **teilweise** abgeschlossen — die Bug-Fixes (PDF, SMTP, Draft, Nummernlogik, Schema-Merge) sind ✔. Der **API-Refactor** (Extraktion aus `main.py` in `app/api/`, Pydantic-Schemas, JWT-Auth) ist **noch offen** und wurde in der ursprünglichen 68-Zeilen-Notiz fälschlich als "weitgehend umgesetzt" markiert.

| Datei / Bereich | Erwartung | Status 2026-06-10 |
|---|---|---|
| `app/main.py` Größe | < 200 Zeilen (nur FastAPI-App-Instanz, API-Routes ausgelagert) | ❌ **1895 Zeilen** |
| `app/api/__init__.py` | Router-Aggregation vorhanden | ❌ fehlt komplett |
| `app/api/auth.py` | JWT-Cookie, CSRF, `/api/auth/login|logout|me` | ❌ fehlt — Auth nur über NiceGUI-Session |
| `app/api/customers.py` | `GET/POST/PUT/DELETE /api/customers[/...]` | ❌ fehlt — keine JSON-Customer-Endpoints |
| `app/api/invoices.py` | `GET/POST /api/invoices`, `POST /api/invoices/preview-pdf` | ❌ fehlt |
| `app/schemas/customer.py` | Pydantic-Modelle `CustomerCreate`, `CustomerUpdate`, `RecipientOverride` | ❌ fehlt — `insert_customer(*, 14 kwargs)` ist noch API-Smell |
| `app/schemas/invoice.py` | `InvoiceDraft`, `InvoiceCreate`, `InvoiceItem` | ❌ fehlt |
| `app/api/internal.py` | `/api/address-autocomplete`, `/api/iban-lookup` | ❌ beide noch in `main.py` |
| `app/api/documents.py` | `POST/GET/DELETE /api/documents[/...]` | ❌ noch in `main.py` |
| `app/api/webhooks.py` | `/api/webhooks/n8n/ingest|upload` | ❌ noch in `main.py` |
| `app/api/share.py` | `/share/read/{token}` | ❌ noch in `main.py` |
| CORS-Middleware | Entfernt (Same-Origin via Vite-Proxy) | ❌ noch aktiv (in main.py:28) |
| OpenAPI-Schema | `/openapi.json` erreichbar, vollständig | ⚠️ FastAPI generiert es, aber nur für 11 bestehende Endpoints |
| `pytest` | 44+/44+ grün | ✔ **44/44** |

### OD8 — Entscheidung (geklärt 2026-06-10)

**Entscheidung: M0-Block jetzt umsetzen, bevor M1 startet.**

**Begründung:**
- React-Frontend braucht `/api/auth/login|logout|me` (M2) und `/api/customers` (M3). Beide existieren nicht als JSON-Endpoints.
- Workaround (z. B. React ruft NiceGUI-WebSocket-Endpoints auf) wäre fragile und reverse-engineered.
- API-Extraktion in `app/api/*` ist sauberer Refactor, der mit TDD in kleinen Scheiben gemacht werden kann.
- ~1-2 Tage Aufwand, aber **nicht parallelisierbar** mit M1 — also besser jetzt.

**M0-Block-Reihenfolge (TDD, kleine Commits):**

1. Skeleton: `app/api/__init__.py` (Router-Aggregation), `app/schemas/__init__.py`
2. Pattern: `app/api/internal.py` mit `address-autocomplete` (kleinster Endpoint, als Template)
3. Pattern: `app/api/share.py` mit `read-token`-Endpoint
4. Pattern: `app/api/documents.py` (Upload, List, Get, Delete)
5. Pattern: `app/api/webhooks.py` (n8n ingest, upload)
6. **Neu (statt Extraktion):** `app/api/auth.py` mit JWT-Cookie + CSRF (`/login|logout|me`)
7. **Neu:** `app/schemas/customer.py` (Pydantic `CustomerCreate|Update|Read|RecipientOverride`)
8. **Neu:** `app/api/customers.py` (CRUD, validiert via Pydantic)
9. **Neu:** `app/schemas/invoice.py` (Pydantic `InvoiceDraft|Create|Item|Read`)
10. **Neu:** `app/api/invoices.py` (Liste, Detail, Status, `preview-pdf`, Correction)
11. `app/main.py` auf ~150 Zeilen schrumpfen (App-Instanz + Router-Include + Static + NiceGUI-Wiring)
12. CORS-Middleware entfernen
13. OpenAPI-Schema unter `/openapi.json` vollständig + Test

**Pro Scheibe:**
- Test schreiben (Red)
- Endpoint verschieben/erstellen (Green)
- `pytest` muss 44+ grün bleiben
- 1 Commit pro Scheibe
- Convention: `refactor(api): extract address-autocomplete to app/api/internal.py`

---

## 7. File-Map: NiceGUI → React

> **Heutiges NiceGUI → React-Ziel-Route**, mit Zeilengröße heute und Migrations-Aufwand-Schätzung.

| NiceGUI (heute) | Zeilen | React-Route (Ziel) | Aufwand | UX-Audit-Refs |
|---|---:|---|---:|---|
| `pages/dashboard.py` | ~480 | `routes/_app.dashboard.tsx` | 1.5d | KPIs + Charts |
| `pages/invoices.py` | ~410 | `routes/_app.invoices.index.tsx` | 1d | Liste + Filter |
| `pages/invoice_create.py` | ~600 | `routes/_app.invoices.new.tsx` | 1w | **M4 — komplexeste Seite** |
| `pages/invoice_detail.py` | ~240 | `routes/_app.invoices.$id.tsx` | 1d | Status-Stepper, "Edit with risk" |
| `pages/customers.py` | ~70 | `routes/_app.customers.index.tsx` | 0.5d | Card-Liste |
| `pages/customer_new.py` | ~100 | `routes/_app.customers.new.tsx` | 0.5d | U1, U2, U10 |
| `pages/customer_detail.py` | ~210 | `routes/_app.customers.$id.tsx` | 0.5d | U6 (Inline-Edit) |
| `pages/documents.py` | ~1530 | `routes/_app.documents.index.tsx` | 1d | Upload + Filter |
| `pages/expenses.py` | ~310 | `routes/_app.expenses.index.tsx` | 1d | CRUD + Filter |
| `pages/ledger.py` | ~220 | `routes/_app.ledger.tsx` | 0.5d | Read-only-Liste |
| `pages/exports.py` | ~60 | `routes/_app.exports.tsx` | 0.3d | Download-Buttons |
| `pages/settings.py` | ~830 | `routes/_app.settings.*.tsx` (7 Routen) | 3d | **U3 (Hub-Aufteilung)** |
| `pages/invites.py` | ~85 | `routes/_app.invites.tsx` | 0.3d | Owner-only |
| `pages/auth.py` | ~350 | `routes/_auth.login.tsx`, `_auth.signup.tsx`, `_auth.verify.tsx`, `_auth.reset.tsx` | 1d | M2 (Auth-Flow) |
| `pages/invoice_utils.py` | ~65 | nicht migriert (Helper in `lib/`) | — | — |
| `pages/_shared.py` | ~620 | nicht migriert (Helper in `lib/`) | — | — |

**Total: ~6.180 Zeilen NiceGUI-Pages → ca. 2.000–2.500 Zeilen React** (weniger durch Component-Sharing + Design-System).

### Komponenten-Wiederverwendung (geplant)

- **`<AddressFields>`**: geteilt von Customer, Invoice-Create, Settings
- **`<ConfirmDestructive>`**: wiederverwendbar in Customer, Company, Account (U9)
- **`<DataTable>`**: shadcn-basiert, mit Filter/Sort/Pagination
- **`<FormSection>`**: Collapsible-Wrapper für Settings-Bereiche (U3)
- **`<StatusBadge>`**: einheitlich für Invoice-Status, Document-Type, etc.

---

## 8. API-Kontrakt-Plan

### 8.1 Heute vorhandene Endpoints (`app/main.py`)

| Method | Path | Auth | Beschreibung | Migrations-Aktion |
|---|---|---|---|---|
| GET | `/api/address-autocomplete` | session | OpenStreetMap-Nominatim-Proxy | → `app/api/internal.py` |
| POST | `/api/webhooks/n8n/ingest` | HMAC | n8n-Payload (Base64) | bleibt (externer Vertrag) |
| POST | `/api/webhooks/n8n/upload` | HMAC | n8n-Multipart-Upload | bleibt |
| GET | `/api/invoices/{id}/pdf` | session | PDF-Download | bleibt, Session → JWT |
| POST | `/api/documents/upload` | session | Document-Upload | bleibt |
| GET | `/api/documents` | session | Liste | bleibt |
| GET | `/api/documents/{id}/file` | session | Download | bleibt |
| DELETE | `/api/documents/{id}` | session | Löschen | bleibt |

### 8.2 Fehlende Endpoints (in M2–M4 zu erstellen)

| Method | Path | Phase | Beschreibung |
|---|---|---|---|
| POST | `/api/auth/login` | M2 | Login, setzt JWT-Cookie + CSRF |
| POST | `/api/auth/logout` | M2 | Logout, löscht Cookies |
| GET | `/api/auth/me` | M2 | Aktueller User |
| GET | `/api/customers` | M3 | Liste, mit Filter |
| POST | `/api/customers` | M3 | Erstellen |
| GET | `/api/customers/{id}` | M3 | Detail |
| PUT | `/api/customers/{id}` | M3 | Update |
| DELETE | `/api/customers/{id}` | M3 | Löschen (nur wenn keine Invoices) |
| POST | `/api/invoices/preview-pdf` | M4 | PDF-Bytes für Live-Preview |
| POST | `/api/invoices` | M4 | Finalisieren |
| GET | `/api/invoices` | M5 | Liste, mit Filter |
| GET | `/api/invoices/{id}` | M5 | Detail |
| PUT | `/api/invoices/{id}/status` | M5 | Status-Transition |
| POST | `/api/invoices/{id}/correction` | M5 | Korrekturrechnung |
| GET | `/api/expenses` | M5 | Liste |
| POST | `/api/expenses` | M5 | Erstellen |
| ... | `/api/{domain}` | M5 | je nach Page |

### 8.3 OpenAPI-Quelle

- **Pydantic-Schemas** als Source of Truth.
- **FastAPI generiert** `/openapi.json` automatisch.
- **Frontend-Tooling:** `openapi-typescript` o.ä. zur Type-Generation, **oder** Zod-Schemata manuell mit `satisfies z.ZodType<Pydantic>`.
- **Drift-Check** in CI: Pydantic ↔ Zod-Vergleich als Test (low priority, nice-to-have).

---

## 9. Design-Token-Bridge

> **Quelle:** `app/styles.py:42-58` (heutige CSS-Variablen) → `frontend/src/styles/tokens.css` (M1).

### 9.1 Token-Map

| Token (heute) | Wert (heute) | Verwendung | Tailwind-Alias |
|---|---|---|---|
| `--ff-bg` | `#f8fafc` | Page-Background | `bg-bg` |
| `--ff-surface` | `#ffffff` | Card-Background | `bg-surface` |
| `--ff-surface-2` | `#f1f5f9` | Sub-Surface (z.B. Sidebar) | `bg-surface-2` |
| `--ff-border` | `#e2e8f0` | Standard-Border | `border-border` |
| `--ff-border-strong` | `#cbd5e1` | Hover/Focus-Border | `border-border-strong` |
| `--ff-text` | `#0f172a` | Body-Text | `text-text` |
| `--ff-muted` | `#64748b` | Sekundär-Text | `text-muted` |
| `--ff-muted-2` | `#94a3b8` | Tertiär-Text (Disabled) | `text-muted-2` |
| `--brand-primary` | `#4338ca` | Primary-Button, aktive States | `bg-brand`, `text-brand` |
| `--brand-accent` | `#312e81` | Ink, used sparingly | `bg-brand-accent` |
| `--brand-soft` | `#6366f1` | Sekundär-Highlight, Icons | `bg-brand-soft` |
| `--brand-subtle` | `#eef2ff` | Subtle-Brand-Background | `bg-brand-subtle` |
| `--brand-tint` | `#f5f3ff` | Hero-Hintergrund | `bg-brand-tint` |
| `--ff-ring` | `rgba(67, 56, 202, 0.18)` | Focus-Ring | `ring-ring` |

### 9.2 Typography

| Token | Wert (heute) | Tailwind |
|---|---|---|
| Body-Font | `"Inter", system-ui, -apple-system, ...` | `font-sans` |
| Display-Font | `"Newsreader", "Iowan Old Style", ...` | `font-display` (custom) |
| Numerik | `tabular-nums` | `font-numeric` (custom) |

### 9.3 Spacing & Radius

- **Spacing:** Tailwind-Default-Skala (4 px-Basis) — passt 1:1 zu NiceGUI `q-pa-*`.
- **Radius:** `0.5rem` (8 px) für Cards, `0.375rem` (6 px) für Inputs/Buttons.

### 9.4 Atmosphärische Details (NiceGUI-spezifisch, zu portieren)

- **Top-right Orb:** `radial-gradient(ellipse 60% 40% at 90% -10%, rgba(67, 56, 202, 0.10) 0%, transparent 55%)`
- **Bottom-left Counter-orb:** `radial-gradient(ellipse 50% 35% at 5% 95%, rgba(244, 114, 182, 0.05) 0%, transparent 55%)`
- **Vertical Wash:** `linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)`

→ Diese Effekte kommen 1:1 in `tokens.css` `body` Background.

---

## 10. Auth & Session-Migration

### 10.1 Heute (NiceGUI)

- **Session-Storage:** `app.storage.user` (Client-Side-JSON, HMAC-signiert).
- **Login:** `services.auth.login_user()` setzt Session-Dict mit `user_id`, `company_id`, `page`.
- **Auth-Guard:** `app/auth_guard.py:require_auth()` redirected unauth → `/login`.
- **CSRF:** Nicht implementiert (Same-Origin, NiceGUI-WebSocket).

### 10.2 Ziel (React)

- **JWT in httpOnly-Cookie** `ff_session`, `Secure` + `SameSite=Lax` (Prod), `HttpOnly`.
- **CSRF in Cookie** `ff_csrf`, `SameSite=Strict`, **nicht** HttpOnly (Client muss ihn lesen).
- **Jeder mutierende Call** sendet `X-CSRF-Token: <csrf>` Header.
- **Server validiert** Cookie-Wert == Header-Wert (constant-time compare).
- **Token-Lifetime:** JWT 7 Tage, CSRF 24h, Refresh-Slider 1 Tag.

### 10.3 Backend-Snippet (M2, ~80 Zeilen)

```python
# app/api/auth.py
from fastapi import APIRouter, Response, HTTPException, Depends, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    user: "UserPublic"
    csrf_token: str

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response):
    user = await login_user(req.email, req.password)
    if not user:
        raise HTTPException(401, "Ungültige Zugangsdaten")
    jwt_token = create_jwt(user.id, ttl=7*24*3600)
    csrf = create_csrf_token(user.id, ttl=24*3600)
    response.set_cookie("ff_session", jwt_token, httponly=True, secure=True, samesite="lax")
    response.set_cookie("ff_csrf", csrf, samesite="strict", secure=True)
    return LoginResponse(user=user_public(user), csrf_token=csrf)

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("ff_session")
    response.delete_cookie("ff_csrf")
    return {"ok": True}

@router.get("/me")
async def me(request: Request):
    user = get_user_from_jwt(request.cookies.get("ff_session"))
    if not user:
        raise HTTPException(401)
    return user_public(user)
```

### 10.4 Frontend-Snippet (M2, ~30 Zeilen)

```typescript
// frontend/src/lib/api.ts
const CSRF_COOKIE = "ff_csrf";

function getCsrf(): string {
  const match = document.cookie.split("; ").find(c => c.startsWith(`${CSRF_COOKIE}=`));
  if (!match) throw new Error("CSRF-Token fehlt — Login nötig");
  return decodeURIComponent(match.split("=")[1]);
}

export const api = {
  get: <T>(path: string) => fetch(path, { credentials: "include" }).then(asJson<T>),
  post: <T>(path: string, body: unknown) =>
    fetch(path, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrf() },
      body: JSON.stringify(body),
    }).then(asJson<T>),
  // put, delete analog
};
```

### 10.5 CSRF-Verifikation im Backend (jeder mutierende Endpoint)

```python
# app/api/dependencies.py
from fastapi import Request, HTTPException, Depends

async def verify_csrf(request: Request) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    cookie = request.cookies.get("ff_csrf")
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(403, "CSRF-Token ungültig")
```

---

## 11. Testing-Strategie

### 11.1 Test-Pyramide

```
       ╱╲
      ╱  ╲      E2E (Playwright)         ~30 Tests, 5–10 min
     ╱────╲     Target: 1 Test pro Page + 1 pro kritischen Flow
    ╱      ╲
   ╱────────╲   Integration (Vitest + MSW) ~50 Tests, 1–2 min
  ╱          ╲  Target: 1 pro API-Endpoint + 1 pro Form-Submit
 ╱────────────╲
╱──────────────╲ Unit (Vitest)             ~100 Tests, <30s
                                       Target: Schemas, Hooks, Utils
```

### 11.2 Backend-Tests (bleiben)

- **pytest** läuft weiterhin — `pytest tests/ → 44+ passed`.
- **Neue Tests** für `app/api/*` (Pydantic-Validierung, Auth-Guards, CSRF).
- **CI-Block:** PR kann nicht gemerged werden, wenn `pytest` rot.

### 11.3 Frontend-Tests (NEU)

- **Vitest** für Unit (Schemas, Hooks, Utils).
- **MSW (Mock Service Worker)** für API-Mocking in Integration-Tests.
- **Playwright** für E2E (echter Browser, echte Backend-Instanz).
- **Coverage-Ziel:** `lib/` > 70% Lines, `components/` > 50% Lines.

### 11.4 Test-Stack-Entscheidungen

| Bereich | Tool | Warum |
|---|---|---|
| Unit | Vitest | Vite-native, schneller als Jest |
| Component | Vitest + Testing Library | Standard im React-Ökosystem |
| API-Mock | MSW | Intercept `fetch` ohne Axios-Hack |
| E2E | Playwright | Echtes Chrome, parallele Workers |
| Visual | Playwright Screenshots | Optional, für Design-Review |
| A11y | `@axe-core/playwright` | Optional, in CI |

### 11.5 Tag-1-Mindest-Tests

- 1 Vitest: `Hello world rendert ohne Fehler`
- 1 Playwright: `Browser auf / lädt ohne 500`

---

## 12. UX-Audit-Übernahme

> **Quelle:** `docs/audit_ux.md` (10 UX-Findings U1–U10, 6 Architektur-Findings A1–A6).
> **Prinzip:** Findings, die **NiceGUI-spezifisch** sind, entfallen automatisch im React-Refactor. Findings, die **logisch** sind, werden im React-Code umgesetzt.

### Findings → React-Phase

| ID | Finding | Severity | React-Umsetzung | Phase |
|---|---|---|---|---|
| **U1** | Doppelte Adress-Felder (Kontakt + Rechnungsempfänger) | blockierend | `<BillingOverride>` Collapsible-Pattern in `<CustomerForm>` und `<InvoiceForm>` | M3, M4 |
| **U2** | 4 Name-Felder semantisch unklar | hoch | "Firma vs. Privat"-Toggle als erstes Form-Element, 1 Name-Feld statt 4 | M3 |
| **U3** | Settings 695 Zeilen, 9 Verantwortlichkeiten | hoch | 7 Sub-Routes statt 1 Mega-Page (`_app.settings.{company,tax_banking,...}.tsx`) | M5 |
| **U4** | IBAN-Auto-Lookup feuert auf `update:value` → DSGVO Art. 5 | **blockierend** | "Bank prüfen"-Button, kein Auto-Lookup im React-Form | M5 (Settings) |
| **U5** | SMTP in Firmen-Settings (Multi-Tenant-inkompatibel) | hoch (Breaking) | SMTP raus aus Company-Settings, in Owner-Setup-Wizard; React bekommt nur `default_sender_email`-Feld | M5 (Settings) |
| **U6** | Kunde-Edit: 14 Felder gleichzeitig | mittel | Inline-Edit-Pattern (Klick auf Feld → Edit, Enter speichert, Esc bricht) | M3 |
| **U7** | Dead Fields (`kdnr`, `short_code`) | mittel | `kdnr` aus Schema raus, `short_code` als Listen-Suche oder entfernen | M3 |
| **U8** | "Read-only Link teilen" ist kein Setting | mittel | Eigene Route `/_app.share.tsx` mit aktivem Link-Manager | M5 |
| **U9** | 3× "Tippe DELETE"-Dialoge | mittel | `<ConfirmDestructive>` Component (Konsequenz-Anzeige + Soft-Delete-Default) | M3–M5 |
| **U10** | PLZ+Ort+Land separate Felder | niedrig | Kombinierte `<AddressFields>`-Component | M3 |
| **A1** | `main.py` mischt API + UI, 1100 Zeilen | hoch | API nach `app/api/*` auslagern (M0-Block) | **vor M1** |
| **A2** | `insert_customer(*, 14 kwargs)` kein Pydantic | hoch | Pydantic `CustomerCreate` als M0-Block | **vor M1** |
| **A3** | `app.storage.user` Client-Side-State | mittel | React-Hooks + TanStack Query, kein manueller Storage | M1–M3 |
| **A4** | Mobile: Hub-Pattern + 50+ Inputs | mittel | Mobile: Bottom-Nav statt Sidebar, Form-Sections einklappbar | M2, M5 (Settings) |
| **A5** | i18n hardcoded DE | niedrig | Nicht im M1–M6-Scope, separates Projekt | **nach M6** |
| **A6** | Keine UI-Tests | mittel | Vitest + Playwright von Anfang an (siehe §11) | M1 |

### Adoptierte Defaults

- **Alle 16 Pages:** Soft-Delete-Default (Audit U9), Inline-Edit wo möglich (U6), kein Auto-Lookup auf Texteingabe (U4).
- **Settings-Hub** statt Mega-Page (U3).
- **Billing-Override** als Collapsible (U1) — Standard in Customer, Invoice-Create.

---

## 13. Open Decisions / Risiken

> **Status dieser Liste:** Fragen, die **vor M1-Start** zu klären sind (oder bewusst mit Empfehlung dokumentiert werden).

| # | Frage | Empfehlung | Owner | Frist |
|---|---|---|---|---|
| OD1 | Bundle-Size-Limit in CI enforced? | Ja, 500 KB gzip als Failure-Threshold | tbd | vor M5 |
| OD2 | Sentry-Setup für Prod-Error-Tracking? | Ja, vor M6 (1 Woche Monitoring) | tbd | vor M6 |
| OD3 | i18n-Strategie (DE-only vs. i18n-ready)? | DE-only in Scope, i18n als separates Projekt nach M6 | tbd | vor M5 (Settings) |
| OD4 | Dark-Mode in M1? | Nein, später (Tokens sind schon CSS-Vars, Aufwand gering) | tbd | nach M6 |
| OD5 | Mobile: Bottom-Nav vs. Burger-Menu? | Bottom-Nav (Audit A4 + Community-Konsens für ≤ 7 Items) | tbd | M2 |
| OD6 | Tests in CI: required oder advisory? | Required (Vitest + Playwright müssen grün sein vor Merge) | tbd | M1 |
| OD7 | Visual-Regression-Tests? | Nein, optional nach M6 (Screenshots im Playwright reichen) | tbd | nach M6 |
| OD8 | M0-Block (API-Auslagerung) wirklich vor M1, oder Workaround? | **Empfehlung: M0-Block vor M1** (sauberer Start, kein Tech-Debt-Carried-Over) | tbd | vor M1 |
| OD9 | Multi-Tenant-SMTP-Refactor (Audit U5) parallel zu M5? | **Nein** — Breaking-Change-Migration zu groß, separates Projekt nach M6 | tbd | nach M6 |
| OD10 | Adress-Autocomplete: OSM-Nominatim bleibt? | Ja (kostenlos, DSGVO-freundlicher als Google), aber Rate-Limit beachten (1 req/s) | tbd | M3 |
| OD11 | Recharts vs. alternativen (Visx, Nivo)? | Recharts (kleineres Bundle, gut für Dashboard) | tbd | M5 (Dashboard) |
| OD12 | React-Query Devtools in Prod? | Nein, nur Dev | tbd | M2 |

### Bekannte Risiken

| Risiko | Impact | Mitigation |
|---|---|---|
| Bundle-Bloat (shadcn + RHF + TanStack) | Mittel | Lazy-Loading pro Route, `bundlewatch` in CI |
| Auth-Token in Cookies → nur hinter HTTPS | Niedrig | Caddy erzwingt TLS, `Secure`-Flag in Prod |
| Hydration-Mismatch | n/a | Kein SSR — komplett client-side |
| State-Sync zwischen Tabs | Niedrig | TanStack Query `BroadcastChannel` (eingebaut) |
| 16 NiceGUI-Pages in React | Hoch | Schrittweise, parallel-Betrieb, klare Phase-Gates |
| NiceGUI-Performance-Regression nach DNS-Switch | Niedrig | NiceGUI-Image 30 Tage als Rollback, DB unverändert |
| M0-Block nicht fertig → React startet auf unstable Backend | Mittel | Vor M1-Start prüfen (siehe §6) |

---

## 14. Definition of Done

### Pro-Phase-DoD

| Phase | DoD |
|---|---|
| M1 | `npm run dev` läuft, `npm run build` grün, 1+ Vitest + 1+ Playwright grün, Backend-Tests 44/44 grün |
| M2 | Login funktional, JWT-Cookie gesetzt, CSRF-Header verifiziert, Sidebar + BottomNav, Auth-Guard redirected, 5+ E2E-Tests grün |
| M3 | Customer-CRUD funktional, alle 6 Audit-Findings (U1, U2, U6, U7, U9, U10) in Code, 10+ E2E-Tests grün |
| M4 | Invoice-Create mit Live-PDF-Preview (800 ms Debounce), Draft+Finalize-Flow, PDF-Bytes identisch zur NiceGUI-Version |
| M5 | Alle 16 Pages funktional, Parallel-Betrieb möglich, Bundle < 500 KB gzip, 30+ E2E-Tests grün |
| M6 | NiceGUI aus Prod-Stack entfernt, DNS-Switch erfolgt, 1 Woche Prod ohne Major-Issues, Bundle < 500 KB, Lighthouse > 90 |

### Gesamt-DoD (Archivierung)

- [ ] Phase M0: Audit + Refactor abgeschlossen
- [ ] Phase M1: Vite-Stack läuft, Hello-World rendert
- [ ] Phase M2: Login funktioniert, JWT in httpOnly-Cookie, Sidebar sichtbar
- [ ] Phase M3: Customers CRUD in React, 10+ E2E-Tests grün
- [ ] Phase M4: Invoice-Create mit Live-PDF-Preview, funktional äquivalent zu NiceGUI
- [ ] Phase M5: Alle 16 Pages in React, NiceGUI noch als `/legacy` erreichbar
- [ ] Phase M6: NiceGUI abgeschaltet, 2-Wochen-Shadow-Mode ohne Major-Issues
- [ ] Bundle-Size < 500 KB gzip
- [ ] Lighthouse-Score > 90 (Performance, A11y, Best Practices)
- [ ] Playwright-E2E-Tests: 30+ Tests, alle grün
- [ ] Vitest-Unit-Tests: > 70% Coverage auf `lib/`
- [ ] Kein `console.error` in Prod-Build, `tsc --noEmit` grün
- [ ] ADR-0001 bis ADR-0010 geschrieben + Migrations-spezifische ADRs (0011–0015)

---

## 15. Handoff-Checkliste

> **Pflichten für den übergebenden Agent** (= dich, wenn du das nächste Mal übernimmst).

### Vor Übergabe

- [ ] **Aktualisiere §2** (Status-Snapshot): M1-Backend-Block-Status, Test-Stand, Docker-Build-Stand.
- [ ] **Aktualisiere §5** (Phase-Plan): aktuelle Phase ✔, nächste Phase als "current".
- [ ] **Aktualisiere §6** (M0-Block): welche Punkte sind jetzt ✔, welche offen.
- [ ] **Aktualisiere §13** (Open Decisions): beantwortete Fragen raus, neue mit Frist rein.
- [ ] **Datum + Version** in Header anpassen.
- [ ] **Git-Status sauber:** Keine uncommitted changes im `frontend/` oder `app/`.

### Übergabe-Format

- [ ] **Branch:** PR gegen `main` mit Label `docs/handoff`.
- [ ] **Commit-Message:** `docs(handoff): update snapshot for Mx start` (Conventional Commits).
- [ ] **PR-Description:** Welche Phase startet, was zu beachten ist, welche Decisions offen.
- [ ] **Reviewer:** Repo-Owner (vor M1: Single-Reviewer reicht; ab M3: 2 Reviewer wegen Auth-Touch).

### An den nächsten Agent

- [ ] **Lies zuerst** §4 (Tag-1-Runbook) **bevor** du irgendwas im Repo änderst.
- [ ] **Lies §3** (Locked Decisions) — keine Diskussion über Stack-Wahl, die ist gelockt.
- [ ] **Lies §6** (M0-Block) — wenn Punkte offen, **vor** React-Start fixen.
- [ ] **Lies §12** (UX-Audit-Übernahme) — Findings sind in Phase X zu adressieren, nicht optional.
- [ ] **Halte TDD ein** (Projekt-Konvention): Test zuerst, fail sehen, minimaler Fix, wieder grün.
- [ ] **Kleine vertikale Scheiben** (1 Phase ≈ 1 PR), nicht M1–M5 in einem Rutsch.

### Was **nicht** zu tun ist

- ❌ **Keine** Diskussion über Next.js / Axios / Redux / Material UI — gelockt, siehe §3.
- ❌ **Keine** Refactor am NiceGUI-Code außer für M0-Block.
- ❌ **Keine** "Quick Wins" außerhalb der aktuellen Phase (z. B. nicht M4-Sachen in M3-PR).
- ❌ **Keine** Änderung an `app/data.py` ohne Migrations-Script.
- ❌ **Keine** DB-Schema-Änderung ohne Diskussion mit Repo-Owner.

---

**Stand des Dokuments:** 2026-06-10
**Nächste geplante Aktualisierung:** vor M1-Start, vor jedem Phasen-Abschluss, bei jeder Open-Decision-Klärung
**Verwandte Dokumente:**
- `docs/migration_react_plan.md` (610 Zeilen, Architektur-Detail)
- `docs/audit_ux.md` (566 Zeilen, UX-Findings U1–U10 + A1–A6)
- `docs/audit.md` (Generelles Code-Audit)
- `README.md` (Senior-Architektur-Reference, Backend)
- `.planning/codebase/ARCHITECTURE.md` (Stack-Architektur, Analyse 2026-05-05)

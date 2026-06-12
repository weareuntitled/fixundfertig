# Migrations-Plan: NiceGUI → React + shadcn/ui

**Datum:** 2026-06-10
**Voraussetzung:** `docs/audit_ux.md` PR 1 + Sprint 2 abgeschlossen (Pydantic-Schemas, API-Split, saubere OpenAPI)
**Geschätzter Aufwand:** 6–8 Wochen (1 Dev, Vollzeit)

## TL;DR

| Phase | Dauer | Ziel | Status |
|-------|-------|------|--------|
| **M0** Audit + Refactor (Vorbereitung) | 2 Wo | Saubere API, Pydantic, OpenAPI | siehe `audit_ux.md` |
| **M1** React-Stack aufsetzen | 2 Tage | Vite + TS + shadcn + TanStack Query | ⏳ |
| **M2** Auth + Layout + Routing | 3 Tage | Login, Sidebar, Theme-Tokens | ⏳ |
| **M3** Erste Seite: Customer-Liste + Detail | 1 Wo | End-to-End-Flow, Design-System-Validierung | ⏳ |
| **M4** Invoice-Create (komplexeste Seite) | 1 Wo | PDF-Preview, Live-Validation | ⏳ |
| **M5** Restliche Pages (Dashboard, Documents, Expenses, Ledger, Exports, Settings, Invites) | 2 Wo | Schritt-für-Schritt, parallel zu NiceGUI | ⏳ |
| **M6** NiceGUI abschalten, Migration-Scripts | 3 Tage | Daten-Migration falls nötig, DNS-Switch | ⏳ |

**Total: ~7 Wochen.** NiceGUI läuft während M3–M5 parallel, Nutzer bekommen keinen Bruch.

---

## Architektur-Entscheidungen (mit Tradeoffs)

### Stack

| Layer        | Tech                                          | Warum                                                            |
|--------------|-----------------------------------------------|------------------------------------------------------------------|
| Build        | **Vite 5** + **TypeScript 5.5 (strict)**     | Schnellster HMR, ESM-native, AI-generierter TS ist verlässlicher |
| Routing      | **TanStack Router**                          | Type-safe routes, Code-Splitting pro Page, keine Typos in URLs |
| Server-State | **TanStack Query v5**                         | Cache, Optimistic Updates, Background Refetch, kein Redux nötig  |
| Forms        | **React Hook Form** + **Zod**                | Pydantic-Validierung 1:1 in Zod spiegelbar, kein Re-Render pro Tastendruck |
| UI-Kit       | **shadcn/ui** (Radix + Tailwind)              | Copy-paste Components, keine Vendor-Lock-in, vollständig anpassbar |
| Styling      | **Tailwind CSS 3.4** + **CSS Variables**     | Design-Tokens zentral, Dark-Mode umsonst                        |
| Schema       | **Zod** (Client) ↔ **Pydantic** (Server)      | OpenAPI generiert beide, kein Drift                              |
| HTTP         | **fetch** (kein Axios)                        | Native, TanStack Query wrappt's, weniger Bundle                  |
| Auth         | **JWT in httpOnly-Cookie** (FastAPI-seitig)   | CSRF-Token separat, XSS-sicher                                   |
| PDF-Preview  | **react-pdf** oder `<iframe src="/api/...pdf">` | iframe ist 0 KB extra, reicht                                   |
| Charts       | **Recharts**                                  | Dashboard passt dazu, kleinere Bundle als ECharts                |
| Icons        | **lucide-react**                              | shadcn-Default, tree-shakeable                                   |
| E2E-Tests    | **Playwright**                                | Echtes Browser-Testing, parallel zu CI                          |
| Unit-Tests   | **Vitest**                                    | Schneller als Jest, Vite-native                                  |
| Lint         | **ESLint** + **Prettier** + **TypeScript**   | Pre-commit-Hook                                                  |
| Deploy       | **Docker** (Vite-Build in `nginx:alpine`)     | Gleicher Stack wie heute, nur neues Service-Compose-File         |

### Warum NICHT Next.js?

- **NiceGUI ist Single-Page-Server-Rendered**: Server-side React ist Overkill
- **Kein SEO nötig** (interne App mit Login)
- **API existiert bereits** (FastAPI), kein BFF nötig
- **Kleineres Bundle**, weniger Konzepte (kein RSC, keine Server Actions)
- **Wenn später SEO kommt**: Migration zu Next.js ist 1-Datei pro Route

### Warum NICHT shadcn mit Material UI / Chakra?

- shadcn/ui gibt dir **Code-Ownership**: Components sind in deinem Repo, kein npm-Update-Bruch
- shadcn = Radix-Primitive (a11y-konform out-of-the-box) + Tailwind
- Deine aktuellen Tailwind-Klassen in `styles.py` → direkte 1:1-Übersetzung

---

## Phase M1 — Stack aufsetzen (2 Tage)

### Repo-Struktur (monorepo, kein Turborepo nötig)

```
fixundfertig/
├── app/                      # Python-Backend (unverändert)
│   ├── api/                  # NEU: FastAPI-Routes (nach M0)
│   ├── ui/                   # NEU: NiceGUI-UI (ausgelagert aus main.py)
│   ├── schemas/              # NEU: Pydantic-Models
│   └── services/
├── frontend/                 # NEU: React-App
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app.tsx           # Router + Layout
│   │   ├── routes/           # Page-Components pro Route
│   │   │   ├── _auth.login.tsx
│   │   │   ├── _auth.signup.tsx
│   │   │   ├── _app.tsx      # Layout mit Sidebar
│   │   │   ├── _app.dashboard.tsx
│   │   │   ├── _app.customers.index.tsx
│   │   │   ├── _app.customers.new.tsx
│   │   │   ├── _app.customers.$id.tsx
│   │   │   ├── _app.invoices.index.tsx
│   │   │   ├── _app.invoices.new.tsx
│   │   │   └── _app.settings.tsx
│   │   ├── components/       # shadcn-Customized
│   │   │   ├── ui/           # shadcn-generiert (button, input, card, …)
│   │   │   ├── forms/        # RHF-Wrapper, AddressInput, etc.
│   │   │   ├── layout/       # Sidebar, BottomNav, TopBar
│   │   │   └── data/         # Tables, KPI-Cards
│   │   ├── lib/              # API-Client, Auth-Helpers
│   │   │   ├── api.ts        # fetch-Wrapper mit Auth-Header
│   │   │   ├── query-client.ts
│   │   │   └── schemas/      # Zod-Mirrors der Pydantic-Models
│   │   ├── hooks/            # useCustomers, useInvoices, …
│   │   └── styles/
│   │       └── tokens.css    # Design-Tokens (Farben, Spacing, Type)
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   └── components.json       # shadcn-Config
├── docker-compose.yml        # erweitert: +frontend-service
└── Dockerfile.frontend       # NEU
```

### Design-Tokens Übersetzung

Deine aktuellen `styles.py`-Werte → CSS-Variablen in `frontend/src/styles/tokens.css`:

```css
:root {
  /* Brand (aus styles.py:53-57) */
  --brand-primary: #4338ca;
  --brand-accent:  #312e81;
  --brand-soft:    #6366f1;
  --brand-subtle:  #eef2ff;

  /* Surface (aus styles.py:42-49) */
  --ff-bg:        #f8fafc;
  --ff-surface:   #ffffff;
  --ff-surface-2: #f1f5f9;
  --ff-border:    #e2e8f0;
  --ff-text:      #0f172a;
  --ff-muted:     #64748b;

  /* Typography (aus styles.py:22-26) */
  --font-sans: "Inter", system-ui, sans-serif;
  --font-display: "Newsreader", "Iowan Old Style", Georgia, serif;
}
```

shadcn-Components nutzen diese Variablen nativ (über `tailwind.config.ts` `colors: { brand: 'var(--brand-primary)' }`).

### Vite-Config (Dev-Proxy)

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react(), TanStackRouterVite()],
  server: {
    proxy: {
      "/api": "http://localhost:8080",   // FastAPI
      "/static": "http://localhost:8080",
    },
  },
});
```

→ Im Dev: Vite auf `:5173`, FastAPI auf `:8080`, kein CORS-Setup nötig weil Same-Origin-Proxy.

---

## Phase M2 — Auth + Layout (3 Tage)

### Auth-Flow

**Heute (NiceGUI):** `app.storage.user` (Client-Side-JSON), Session-Cookie, `require_auth()`-Helper

**Ziel (React):** JWT in httpOnly-Cookie + CSRF-Token, `useAuth()`-Hook

**FastAPI-Änderungen:**

```python
# app/api/auth.py (neu, ~200 Zeilen)
from fastapi import APIRouter, Response, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    user: UserPublic
    csrf_token: str

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response):
    # ... validierung
    token = create_jwt(user_id)
    csrf = create_csrf_token()
    response.set_cookie("ff_session", token, httponly=True, secure=True, samesite="lax")
    response.set_cookie("ff_csrf", csrf, samesite="strict")
    return LoginResponse(user=user_public, csrf_token=csrf)

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("ff_session")
    response.delete_cookie("ff_csrf")

@router.get("/me", response_model=UserPublic)
async def me(user = Depends(get_current_user_from_jwt)):
    return user
```

**React-Seite:**

```typescript
// frontend/src/lib/auth.ts
export const useAuth = () => {
  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api.get("/api/auth/me"),
    retry: false,
  });
  return { user: query.data, isLoading: query.isLoading };
};

export const useLogin = () => {
  return useMutation({
    mutationFn: (creds: LoginRequest) => api.post("/api/auth/login", creds),
    onSuccess: () => queryClient.invalidateQueries(["auth"]),
  });
};
```

**Defense-in-Depth:** Jeder mutating API-Call (POST/PUT/DELETE) muss `X-CSRF-Token`-Header senden, FastAPI verifiziert.

### Layout-Migration

**Heute:** `main.py:2029` (`@ui.page("/")`) rendert Sidebar + Content, Routing via `app.storage.user["page"]`

**Ziel:** TanStack Router mit File-Based-Routing

```typescript
// frontend/src/routes/_app.tsx
export const Route = createFileRoute("/_app")({
  beforeLoad: requireAuth,
  component: AppShell,
});

function AppShell() {
  return (
    <div className="flex h-screen">
      <Sidebar className="hidden md:flex" />
      <main className="flex-1 overflow-auto pb-16 md:pb-0">
        <Outlet />
      </main>
      <BottomNav className="md:hidden" />
    </div>
  );
}
```

**Sidebar-Daten:** 1:1 aus `main.py:1302-1353` portieren, aber als Config-Objekt:

```typescript
// frontend/src/lib/nav-items.ts
export const navItems = [
  { id: "dashboard",   label: "Dashboard",  icon: LayoutDashboard, to: "/dashboard" },
  { id: "invoices",    label: "Rechnungen", icon: FileText,        to: "/invoices" },
  { id: "customers",   label: "Kunden",     icon: Users,           to: "/customers" },
  { id: "documents",   label: "Belege",     icon: Folder,          to: "/documents" },
  { id: "expenses",    label: "Ausgaben",   icon: Receipt,         to: "/expenses" },
  { id: "ledger",      label: "Buchhaltung",icon: BookOpen,        to: "/ledger" },
  { id: "exports",     label: "Exports",    icon: Download,        to: "/exports" },
] as const;
```

---

## Phase M3 — Erste Seite: Customers (1 Woche, Pilot)

**Warum zuerst?** Mittlere Komplexität, alle Patterns (Liste + Detail + Form), aber nicht so komplex wie Invoice-Create. Wenn das steht, ist das Design-System validiert.

### Route: `/customers`

**NiceGUI-Heute:** `pages/customers.py` (2.7 KB, einfache Card-Liste)
**NiceGUI-Edit:** `pages/customer_detail.py` (8.5 KB, 14 Felder)
**NiceGUI-New:** `pages/customer_new.py` (4 KB)

**React-Ziel:**

| Datei                                       | Zeilen-Ziel | Was                                  |
|---------------------------------------------|-------------|--------------------------------------|
| `routes/_app.customers.index.tsx`           | <200        | Liste mit Suche + Filter             |
| `routes/_app.customers.new.tsx`             | <250        | Create-Form (RHF + Zod, Audit U1+U2) |
| `routes/_app.customers.$id.tsx`             | <300        | Detail + Inline-Edit (Audit U6)      |
| `components/forms/customer-form.tsx`        | <250        | Shared Form-Component                |
| `components/forms/address-fields.tsx`       | <150        | Adress-Block mit Autocomplete        |
| `components/forms/billing-override.tsx`     | <150        | Optional Override (Audit U1)         |
| `lib/hooks/use-customers.ts`                | <100        | TanStack-Query-Wrapper               |
| `lib/schemas/customer.ts`                   | <100        | Zod-Spiegel von Pydantic              |

**Total: ~1500 Zeilen React für 3 Pages** — vergleichbar mit NiceGUI (~14 KB), aber typed, testbar, geteilt.

### TanStack Query Pattern

```typescript
// frontend/src/lib/hooks/use-customers.ts
export const useCustomers = (filters?: CustomerFilters) =>
  useQuery({
    queryKey: ["customers", filters],
    queryFn: () => api.get<Customer[]>("/api/customers", { params: filters }),
  });

export const useCustomer = (id: number) =>
  useQuery({
    queryKey: ["customers", id],
    queryFn: () => api.get<Customer>(`/api/customers/${id}`),
    enabled: !!id,
  });

export const useCreateCustomer = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CustomerCreate) => api.post("/api/customers", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      toast.success("Kunde angelegt");
    },
  });
};

export const useUpdateCustomer = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CustomerUpdate }) =>
      api.put(`/api/customers/${id}`, data),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      qc.invalidateQueries({ queryKey: ["customers", id] });
    },
  });
};
```

### Form-Pattern (RHF + Zod)

```typescript
// frontend/src/components/forms/customer-form.tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { customerCreateSchema, type CustomerCreate } from "@/lib/schemas/customer";

export function CustomerForm({ defaultValues, onSubmit }: Props) {
  const form = useForm<CustomerCreate>({
    resolver: zodResolver(customerCreateSchema),
    defaultValues: defaultValues ?? { typ: "firma", name: "", country: "DE" },
  });

  const { watch, setValue, handleSubmit, control, formState } = form;
  const typ = watch("typ");
  const hasOverride = watch("recipient_override") !== null;

  return (
    <Form onSubmit={handleSubmit(onSubmit)}>
      <RadioGroup value={typ} onValueChange={(v) => setValue("typ", v as any)}>
        <RadioGroupItem value="firma" label="Firma" />
        <RadioGroupItem value="privat" label="Privatperson" />
      </RadioGroup>

      <FormField name="name" label={typ === "firma" ? "Firmenname" : "Vor- und Nachname"} required />

      <AddressFields control={control} />

      <Separator />

      <Collapsible open={hasOverride} onOpenChange={(o) =>
        setValue("recipient_override", o ? {} : null)
      }>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" type="button">
            <ChevronRight /> Abweichende Rechnungsadresse
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <BillingOverrideFields control={control} />
        </CollapsibleContent>
      </Collapsible>

      <Button type="submit" disabled={formState.isSubmitting}>
        {formState.isSubmitting ? <Spinner /> : "Speichern"}
      </Button>
    </Form>
  );
}
```

**Audit-Umsetzung:** U1 (Override-Pattern), U2 (Typ-Toggle), U4 (kein Auto-Lookup), U10 (PLZ/Ort kombiniert) — alle in 1 Component.

### Validierung (Zod ↔ Pydantic 1:1)

**Server (Pydantic):**
```python
class CustomerCreate(BaseModel):
    typ: Literal["firma", "privat"] = "firma"
    name: str = Field(min_length=1, max_length=200)
    email: str = ""
    # ...
```

**Client (Zod):**
```typescript
export const customerCreateSchema = z.object({
  typ: z.enum(["firma", "privat"]).default("firma"),
  name: z.string().min(1, "Pflichtfeld").max(200),
  email: z.string().email("Ungültige Email").or(z.literal("")),
  // ...
}) satisfies z.ZodType<CustomerCreate>;
```

`satisfies z.ZodType` stellt sicher, dass Pydantic-Output und Zod-Schema strukturell identisch sind. Bei Drift → TypeScript-Error.

### Custom shadcn-Components

Du brauchst ~10 von ~50 shadcn-Components:
- `button`, `input`, `label`, `textarea`, `select`
- `card`, `dialog`, `popover`, `dropdown-menu`
- `form`, `radio-group`, `checkbox`, `switch`
- `table`, `badge`, `tabs`, `separator`
- `toast` (sonner), `skeleton`, `avatar`

Install via `npx shadcn@latest add button input ...`. Customizations in `components/ui/`.

### Tests (Vitest + Playwright)

```typescript
// customer-form.test.tsx
import { render, screen, userEvent } from "@/test-utils";
import { CustomerForm } from "./customer-form";

it("zeigt Rechnungsadresse-Felder erst nach Override-Toggle", async () => {
  render(<CustomerForm onSubmit={vi.fn()} />);
  expect(screen.queryByLabelText(/rechnungsempfänger/i)).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /abweichende/i }));
  expect(screen.getByLabelText(/rechnungsempfänger/i)).toBeVisible();
});
```

---

## Phase M4 — Invoice-Create (1 Woche, komplexeste Seite)

**NiceGUI-Heute:** `pages/invoice_create.py` (24 KB, 700+ Zeilen)
- Customer-Selector mit Inline "Neuen Kunden hinzufügen"
- Datum-Picker
- VAT-Toggle
- Line-Item-Dialog
- Live HTML-Summary + PDF-Preview
- "Rechnung finalisieren"

**React-Ziel:** Die einzige "echte" Komplexität ist Live-PDF-Preview. Sonst Standard-Form.

**Live-Preview-Pattern:**
```typescript
// frontend/src/routes/_app.invoices.new.tsx
function InvoiceNewPage() {
  const form = useForm<InvoiceDraft>({ ... });

  // Debounced: rendere PDF alle 800ms nach letzter Änderung
  const watched = form.watch();
  const debouncedData = useDebounce(watched, 800);

  const preview = useQuery({
    queryKey: ["invoice-preview", debouncedData],
    queryFn: () => api.post("/api/invoices/preview-pdf", debouncedData, { responseType: "blob" }),
    enabled: !!debouncedData.items?.length,
  });

  return (
    <div className="grid lg:grid-cols-2">
      <Form>{/* ... Form-Felder */}</Form>
      <div className="hidden lg:block sticky top-0 h-screen">
        {preview.data ? (
          <iframe src={URL.createObjectURL(preview.data)} className="w-full h-full" />
        ) : (
          <Skeleton className="h-full" />
        )}
      </div>
    </div>
  );
}
```

**Backend-Endpoint:**
```python
# app/api/invoices.py
@router.post("/preview-pdf", response_class=Response)
async def preview_pdf(draft: InvoiceDraft):
    pdf_bytes = render_invoice_to_pdf_bytes(draft.dict())
    return Response(content=pdf_bytes, media_type="application/pdf")
```

→ kein State, kein Cache, jedes Mal frisch. Bei 800ms Debounce maximal 1 Render/Sekunde.

---

## Phase M5 — Restliche Pages (2 Wochen)

Parallel-Strategie: NiceGUI und React laufen auf verschiedenen Routen:
- `https://app.example.com/old/*` → NiceGUI
- `https://app.example.com/*` → React

User werden per Cookie-Banner auf neue UI hingewiesen. Pro Page:
- 1 PR Backend (Endpoint in `app/api/`, ggf. Pydantic-Schema)
- 1 PR Frontend (Page + Tests)

Reihenfolge (nach Komplexität, low-hanging fruit zuerst):
1. **Invites** (klein, ~3h, validiert Auth-Flow)
2. **Exports** (nur Download-Buttons, ~3h)
3. **Documents** (Upload, ~1d, File-Input-Pattern)
4. **Expenses** (CRUD, ~1d, Form-Pattern wiederverwendet)
5. **Ledger** (Read-only-Liste, ~0.5d)
6. **Invoices-Liste** (Read-only + Filter, ~1d, Tabelle mit TanStack Table)
7. **Invoice-Detail** (Status-Stepper, Aktionen, ~1d)
8. **Dashboard** (KPIs + Charts, ~1.5d, validiert Visualisierungs-Pattern)
9. **Settings** (komplexeste, alle 7 Sub-Routes aus Audit U3, ~3d)

---

## Phase M6 — NiceGUI abschalten (3 Tage)

### Voraussetzungen
- Alle 16 Pages in React funktional equivalent
- E2E-Tests grün (Playwright läuft beide Stacks parallel)
- 2 Wochen Shadow-Mode im Prod (User können zwischen Old/New wechseln)

### Schritte
1. **DNS-Switch**: React übernimmt `/`, NiceGUI auf `/legacy` umleiten
2. **Daten-Migration**: Keine (gleiche DB, gleiche Endpoints)
3. **Storage-Cleanup**: `app.storage.user` JSONs in `.nicegui/` löschen
4. **Compose-Cleanup**: NiceGUI-UI aus `docker-compose.prod.yml` entfernen
5. **Dependencies**: `nicegui` aus `pyproject.toml` entfernen (nur `fastapi` als Frontend-Server)
6. **Bundle-Size-Check**: Sicherstellen dass `frontend/dist/` <500 KB gzip
7. **Monitoring**: 1 Woche Error-Tracking (Sentry o.ä.) nur für React-Stack

### Rollback-Plan
- DNS-Eintrag revertierbar (TTL 300s)
- NiceGUI-Image noch 30 Tage in Registry behalten
- DB-Schema identisch, Daten rückwärtskompatibel

---

## Backend-Changes die VOR React-Start fertig sein müssen

| Datei                        | Änderung                                                                | Quelle       |
|------------------------------|-------------------------------------------------------------------------|--------------|
| `app/main.py` (1895 → 100)   | Nur FastAPI-App-Instanz, alles andere in `app/api/`, `app/ui/`         | Audit A1     |
| `app/api/__init__.py` (neu)  | Router-Aggregation                                                      | Audit A1     |
| `app/api/customers.py` (neu) | `GET/POST/PUT/DELETE /api/customers[/...]`                              | M3           |
| `app/api/invoices.py` (neu)  | `GET/POST /api/invoices`, `POST /api/invoices/preview-pdf`              | M4           |
| `app/api/auth.py` (neu)      | JWT-Cookie, CSRF, `/api/auth/login`, `/me`, `/logout`                   | M2           |
| `app/schemas/customer.py`    | `CustomerCreate`, `CustomerUpdate`, `RecipientOverride` (Pydantic)     | Audit A2     |
| `app/schemas/invoice.py`     | `InvoiceDraft`, `InvoiceCreate`, `InvoiceItem`                          | M4           |
| `app/api/internal.py`        | `/api/address-autocomplete`, `/api/iban-lookup`                          | M3           |
| CORS-Middleware              | Entfernen (Same-Origin via Vite-Proxy)                                  | M1           |

**Geschätzt:** 1 Woche Vollzeit, alle parallel zu M1–M2 möglich.

---

## Was wir VERLIEREN und was wir GEWINNEN

### Verlust
- **Python-only-Stack** → 2 Sprachen, 2 Lint-Setups, 2 CI-Pipelines
- **NiceGUI-Reload-Geschwindigkeit** (Python-Webserver) → Vite-HMR ist schneller, aber Build dauert
- **Einfaches Deployment** (1 Container) → 2 Container (Vite-Build in nginx + FastAPI)

### Gewinn
- **Type-Safety**: TypeScript fängt 80% der Bugs vor dem Browser
- **Component-Wiederverwendung**: shadcn-Components, RHF-Hooks, Zod-Schemas geteilt
- **Performance**: Code-Splitting, Lazy-Loading, kein Full-Page-Reload
- **E2E-Tests**: Playwright auf echtem Chrome
- **AI-Iteration**: AI-generiertes React + TS ist verlässlicher als NiceGUI-Python
- **Hireability**: React-Devs sind 10x verfügbarer als NiceGUI-Devs
- **Mobile**: React + Tailwind macht native-feeling Mobile trivial
- **Design-Iteration**: shadcn-Theme-Tokens → 1 Datei ändert das ganze UI

### Risiken
- **Bundle-Bloat**: shadcn + Recharts + RHF = ~200 KB. Akzeptabel.
- **Hydration-Mismatch**: N/A (kein SSR)
- **Auth-Token in Cookies**: Erfordert `Secure`-Flag in Prod → funktioniert nur hinter HTTPS-Caddy
- **State-Sync zwischen Tabs**: TanStack Query broadcast via `BroadcastChannel` (eingebaut)

---

## Definition of Done (für die ganze Migration)

- [ ] Phase M0: Audit + Refactor abgeschlossen
- [ ] Phase M1: Vite-Stack läuft, Hello-World rendert
- [ ] Phase M2: Login funktioniert, JWT in httpOnly-Cookie, Sidebar sichtbar
- [ ] Phase M3: Customers Create/Read/Update/Delete in React, 10+ E2E-Tests grün
- [ ] Phase M4: Invoice-Create mit Live-PDF-Preview, funktional equivalent zu NiceGUI
- [ ] Phase M5: Alle 16 Pages in React, NiceGUI noch als `/legacy` erreichbar
- [ ] Phase M6: NiceGUI abgeschaltet, 2-Wochen-Shadow-Mode ohne Major-Issues
- [ ] Bundle-Size <500 KB gzip
- [ ] Lighthouse-Score >90 (Performance, A11y, Best Practices)
- [ ] Playwright-E2E-Tests: 30+ Tests, alle grün
- [ ] Vitest-Unit-Tests: >70% Coverage auf `lib/`
- [ ] Kein `console.error` in Prod-Build
- [ ] ADR-0001 bis ADR-0010 geschrieben + Migrations-spezifische ADRs (0011–0015)

---

## Quellen

- TanStack Router/Query Docs (2024) — tanstack.com
- shadcn/ui Docs — ui.shadcn.com
- Vite Guide — vitejs.dev
- React Hook Form + Zod Patterns — rtk-query.com/blog
- Baymard Institute — Checkout-Form-Studies
- Reddit r/reactjs (2024) — Community-Konsens: "TanStack Query > Redux für 95% der Apps"
- "Tao of React" — Alex Kondov (2023) — Composition-Patterns
- "Clean Architecture" — Robert C. Martin (2017) — Backend-Split als Hexagonal-Architektur

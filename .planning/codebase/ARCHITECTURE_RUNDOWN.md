# FixundFertig Architecture Full Rundown

**Analysis Date:** 2026-05-05

---

## System Overview

FixundFertig is a German invoicing/ERP SaaS platform built with Python, NiceGUI, and FastAPI. It provides complete invoice management with document ingestion, customer management, PDF generation, and webhook integrations.

---

## High-Level Architecture

```mermaid
flowchart TB
    subgraph Client["Browser (Client)"]
        Browser["Web Browser"]
    end

    subgraph Proxy["Caddy Reverse Proxy"]
        Caddy["Port 80/443<br/>TLS Termination"]
    end

    subgraph App["FixundFertig App"]
        UI[NiceGUI UI<br/>Port 8080]
        API[FastAPI<br/>REST Endpoints]
    end

    subgraph Services["Business Services"]
        Auth[Auth Service]
        Invoice[Invoice Service]
        Doc[Document Service]
        PDF[PDF Renderer]
        Storage[Storage Service]
    end

    subgraph Data["Data Layer"]
        SQLite[("SQLite<br/>database.db")]
        Files[("File Storage<br/>/invoices, /documents")]
        Cache[(Redis<br/>Optional)]
    end

    subgraph External["External Integrations"]
        N8N[n8n Automation]
        S3[AWS S3]
        SMTP[Email/SMTP]
    end

    Client -->|HTTPS| Caddy
    Caddy -->|WebSocket| UI
    Caddy -->|REST| API
    UI --> Auth
    API --> Auth
    UI --> Invoice
    API --> Invoice
    Invoice --> PDF
    Doc --> Storage
    Invoice --> Files
    SQLite <-.->|SQLModel| Invoice
    SQLite <-.->|SQLModel| Doc
    Storage -->|boto3| S3
    API <-->|Webhook| N8N
    Invoice -->|SMTP| SMTP
    Cache -.->|optional| UI
```

---

## Application Structure

```mermaid
graph TB
    subgraph app["app/ Directory"]
        main["main.py<br/>(2000+ lines)"]
        data["data.py<br/>(Models)"]
        
        subgraph pages["pages/"]
            auth["auth.py"]
            dash["dashboard.py"]
            cust["customers.py"]
            inv["invoices.py"]
            docs["documents.py"]
            sets["settings.py"]
        end
        
        subgraph services["services/"]
            s_auth["auth.py"]
            s_inv["invoices.py"]
            s_doc["documents.py"]
            s_storage["storage.py"]
            s_pdf["invoice_pdf.py"]
            s_email["email.py"]
            s_blob["blob_storage.py"]
        end
        
        integrations["integrations/"]
            n8n["n8n_client.py"]
    end

    main --> data
    main --> pages
    main --> services
    pages --> services
    services --> data
    integrations --> services
```

---

## Request Flow: Browser → UI

```mermaid
sequenceDiagram
    participant B as Browser
    participant C as Caddy
    participant N as NiceGUI UI
    participant A as Auth Guard
    participant S as Services
    participant D as SQLite

    B->>C: HTTPS Request
    C->>N: Forward to :8080
    N->>A: Check session
    A->>A: Validate cookie
    alt Authenticated
        A->>S: Call service
        S->>D: Query data
        D-->>S: Return results
        S-->>N: Data
        N-->>B: Rendered UI
    else Not Authenticated
        A-->>N: Redirect to login
        N-->>B: Login page
    end
```

---

## Request Flow: External API

```mermaid
sequenceDiagram
    participant E as External<br/>(n8n, API)
   participant C as Caddy
   participant F as FastAPI
   participant V as Validation<br/>(Pydantic)
   participant A as Auth
   participant S as Services
   participant D as SQLite

    E->>C: POST /api/webhooks/n8n/ingest
    C->>F: Forward to :8080
    F->>V: Validate payload
    V->>A: Verify HMAC signature
    alt Valid
        A->>S: Process webhook
        S->>D: Insert/Update
        D-->>S: Confirm
        S-->>F: Success
        F-->>E: 200 OK
    else Invalid
        F-->>E: 401 Unauthorized
    end
```

---

## Server Integration Architecture

```mermaid
flowchart LR
    subgraph Docker["Docker Compose Stack"]
        subgraph Frontend["Frontend Service"]
            Caddy1["Caddy<br/>:80/:443"]
        end
        
        subgraph App["App Service"]
            FF["FixundFertig<br/>:8080"]
        end
        
        subgraph Automation["Automation"]
            N8N["n8n<br/>:5678"]
            PG[("PostgreSQL")]
        end
        
        subgraph Cache["Cache"]
            Redis2[("Redis")]
        end
    end

    Caddy1 --> FF
    FF --> N8N
    N8N --> PG
    FF --> Redis2
    
    subgraph External["External"]
        S3[(AWS S3)]
        SMTP[Email]
    end
    
    FF -.->|optional| S3
    FF -.-> SMTP
```

---

## Deployment Configuration

```mermaid
graph LR
    subgraph Production["Production Stack"]
        direction TB
        LB["Caddy Load Balancer"]
        APP["Python App<br/>(NiceGUI+FastAPI)"]
        DB[(PostgreSQL)]
        CACHE[(Redis)]
        N8N[n8n]
        
        LB --> APP
        APP --> DB
        APP --> CACHE
        APP --> N8N
        N8N --> DB
    end
    
    subgraph Storage["Storage Layer"]
        S3[(AWS S3)]
        FS["Local FS"]
    end
    
    APP -->|cloud| S3
    APP -->|default| FS
```

---

## Database Schema Overview

```mermaid
erDiagram
    User ||--o{ Company : owns
    Company ||--o{ CompanyUser : has
    Company ||--o{ Customer : has
    Company ||--o{ Invoice : has
    Company ||--o{ Document : has
    Company ||--o{ WebhookEvent : has
    Customer ||--o{ Invoice : has
    Invoice ||--o{ InvoiceItem : has
    Invoice ||--o{ Document : references
    
    User {
        int id PK
        string email
        string password_hash
        bool is_owner
    }
    
    Company {
        int id PK
        string name
        string address
        string webhook_url
        string n8n_secret
    }
    
    Customer {
        int id PK
        int company_id FK
        string name
        string email
        string address
    }
    
    Invoice {
        int id PK
        int company_id FK
        int customer_id FK
        string invoice_number
        date date
        decimal amount
        string status
    }
    
    Document {
        int id PK
        int company_id FK
        string filename
        string storage_key
        string mime_type
    }
```

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Web Framework** | NiceGUI + FastAPI | Python 3.11+ |
| **Database** | SQLite (default) / PostgreSQL (prod) | SQLModel ORM |
| **PDF Generation** | ReportLab, fpdf2 | Latest |
| **Authentication** | Custom session + HMAC | bcrypt, passlib |
| **Storage** | Local filesystem, AWS S3 | boto3 |
| **Automation** | n8n | Latest |
| **Proxy** | Caddy 2 | Latest |
| **Runtime** | Docker, uvicorn | Latest |

---

## Key Integration Points

### n8n Integration
```mermaid
flowchart LR
    N8N[n8n<br/>Automation] -->|POST| WH[Webhook<br/>/api/webhooks/n8n/ingest]
    WH -->|HMAC Verify| APP[FixundFertig]
    APP -->|Store Document| S3[(S3 or FS)]
    APP -->|Update DB| DB[(SQLite)]
```

### S3 Blob Storage
```mermaid
flowchart TB
    Upload[File Upload] --> Check{Storage Config}
    Check -->|local| LocalFS["Local Storage<br/>/storage/documents"]
    Check -->|s3| S3["AWS S3<br/>bucket/documents"]
```

---

## Component Responsibilities

| Component | File | Responsibility |
|-----------|------|-------------|
| `main.py` | `app/main.py` | FastAPI app, routing, middleware |
| `data.py` | `app/data.py` | SQLModel entities |
| `pages/*` | `app/pages/*.py` | NiceGUI UI renderers |
| `services/*` | `app/services/*.py` | Business logic |
| `renderer.py` | `app/renderer.py` | PDF generation |
| `n8n_client.py` | `app/integrations/n8n_client.py` | n8n webhook client |

---

## Environment Variables

### Required
- `OWNER_EMAIL` - Initial owner account
- `OWNER_PASSWORD` - Initial owner password
- `APP_DOMAIN` - Production domain
- `STORAGE_SECRET` - Session signing secret (32+ chars)

### Optional
- `REDIS_URL` - Redis caching
- `N8N_SECRET` - n8n integration
- `AWS_*` - S3 credentials
- `SMTP_*` - Email settings

---

## Security Architecture

```mermaid
flowchart TB
    subgraph Security["Security Layers"]
        TLS["TLS 1.3"]
        HMAC["HMAC Signature"]
        Session["Session Cookie"]
        Auth["Auth Middleware"]
    end
    
    Request --> TLS --> HMAC --> Session --> Auth
```

---

*Full architecture rundown: 2026-05-05*
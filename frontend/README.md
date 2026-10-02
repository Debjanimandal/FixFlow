# FixFlow Frontend

**Next.js frontend for the FixFlow autonomous self-healing platform.**

This service is fully independent. It communicates with the backend only via HTTP — no shared code, no shared dependencies.

---

## Stack

- **Framework**: Next.js 16 (App Router)
- **Runtime**: React 19, TypeScript
- **Styling**: Tailwind CSS v4
- **Animation**: Framer Motion

---

## Setup

### 1. Install dependencies
```bash
npm install
```

### 2. Environment
`.env.local` is pre-configured for local development:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_DEMO_MODE=false
```

Change `NEXT_PUBLIC_API_URL` if your backend runs on a different host or port.

Set `NEXT_PUBLIC_DEMO_MODE=true` to explore the UI without a running backend (uses mock data, login with `demo`).

### 3. Start dev server
```bash
npm run dev
```

App: http://localhost:3000

---

## Pages

| Route | Description |
|---|---|
| `/` | Redirects to `/login` or `/dashboard` |
| `/login` | Owner login (JWT auth) |
| `/dashboard` | Incident overview + stats |
| `/dashboard/incidents/{id}` | Incident detail — Analysis / Patch / Audit tabs |
| `/dashboard/repositories` | Connected GitHub repositories |
| `/dashboard/settings` | Integration status, webhook endpoints, env guide |

---

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx          Root layout (fonts, global CSS)
│   ├── page.tsx            Root redirect
│   ├── globals.css         Design system tokens (CSS variables)
│   ├── login/
│   │   └── page.tsx        Login page
│   └── dashboard/
│       ├── layout.tsx      Sidebar + auth guard
│       ├── page.tsx        Dashboard home (incident stats)
│       ├── incidents/
│       │   └── [id]/       Incident detail page
│       ├── repositories/   Repository management
│       └── settings/       Platform settings
├── lib/
│   ├── api-client.ts       Typed HTTP client for all backend endpoints
│   ├── demo-data.ts        Mock data for demo mode
│   └── design-tokens.ts    Shared design constants
├── public/                 Static assets
├── .env.local              Frontend env vars (backend URL, demo mode)
├── next.config.ts
├── package.json
└── tsconfig.json
```

---

## Design System

Dark monochrome control center aesthetic — defined in `app/globals.css`:

| CSS Variable | Usage |
|---|---|
| `--bg-main` | Main background (`#0a0a0a`) |
| `--bg-card` | Card/panel background |
| `--text-primary` | Primary text |
| `--text-muted` | Secondary/muted text |
| `--border-subtle` | Subtle borders |
| `--accent` | Accent colour (white) |

---

## API Client

All backend calls go through `lib/api-client.ts`. It:
- Reads `NEXT_PUBLIC_API_URL` for the base URL
- Attaches the JWT token from `localStorage` to every request
- Intercepts calls in demo mode and returns mock data instead
- Throws typed errors with `.detail` on API failures

---

## Building for Production

```bash
npm run build
npm run start
```

Deploy to Vercel by connecting the `frontend/` directory as the root.

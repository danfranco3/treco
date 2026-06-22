# Deploying Treco

Full self-hosting guide for production. Covers Railway, Render, Fly.io, and a bare VPS with systemd.

All four targets need the same things: a PostgreSQL database, a backend process, a frontend process, and a few mandatory environment variables. The differences are in how you wire them together.

---

## Environment Variables Reference

### Backend — Required

| Variable | Description |
|----------|-------------|
| `JWT_SECRET` | Signs all JWTs. Must be at least 32 random bytes. Generate with `openssl rand -hex 32`. **Never use the default `dev-secret-change-in-production` in production.** |
| `DATABASE_URL` | SQLAlchemy async connection string. See format below. |
| `DATABASE_MODE` | Must be `postgres` when using PostgreSQL. Default is `sqlite`. |

### Backend — Recommended

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON list of allowed frontend origins. Must include your frontend URL or browsers will block all API calls. |
| `BACKEND_URL` | `http://localhost:8001` | Public URL of the backend. Used by agent subprocesses to reach the API. |
| `FRONTEND_URL` | `http://localhost:3000` | Public URL of the frontend. Used for GitHub OAuth redirect URIs. |

### Backend — LLM (for criteria extraction)

At least one key enables LLM-based acceptance criteria extraction. If neither is set, Treco falls back to parsing markdown checkboxes.

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Used when `LLM_PROVIDER=anthropic` (default). |
| `OPENAI_API_KEY` | Used when `LLM_PROVIDER=openai`. |
| `LLM_PROVIDER` | `anthropic` or `openai`. Default: `anthropic`. |

### Backend — GitHub OAuth (optional)

| Variable | Description |
|----------|-------------|
| `GITHUB_CLIENT_ID` | From your GitHub OAuth app. |
| `GITHUB_CLIENT_SECRET` | Keep secret — never commit or log. |

### Frontend — Build-time

These are baked into the Next.js bundle at build time. Changing them requires a rebuild.

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Public URL of the backend. Must be reachable from the user's browser. |
| `NEXT_PUBLIC_WORKSPACE_ID` | Default workspace shown in the dashboard. Default: `default`. |

### PostgreSQL connection string format

```
postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME
```

The `+asyncpg` driver is required. The synchronous `psycopg2` driver will not work with the async engine.

---

## Railway

Railway provisions containers from a `Dockerfile` and can attach a managed PostgreSQL database.

### 1. Create a project

```bash
# Install the Railway CLI
npm install -g @railway/cli
railway login
railway init
```

Or create a project from the [Railway dashboard](https://railway.app/dashboard) by connecting your GitHub fork.

### 2. Add PostgreSQL

In the Railway dashboard, click **New** → **Database** → **PostgreSQL**. Railway creates a `DATABASE_URL` variable in the database service.

### 3. Deploy the backend

Create a backend service from the `./backend` directory (or a `Dockerfile` pointing at it).

Add these environment variables in the Railway service settings:

```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}   # reference Railway's managed DB
DATABASE_MODE=postgres
JWT_SECRET=$(openssl rand -hex 32)
CORS_ORIGINS=["https://your-frontend.up.railway.app"]
BACKEND_URL=https://your-backend.up.railway.app
FRONTEND_URL=https://your-frontend.up.railway.app
ANTHROPIC_API_KEY=sk-ant-...              # optional but recommended
```

Railway injects `PORT` automatically. The `Dockerfile` CMD already uses `--port 8001`, so override the start command:

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Or set `PORT=8001` in the Railway environment and leave the Dockerfile CMD unchanged.

The `entrypoint.sh` runs `alembic upgrade head` before starting — migrations run automatically on every deploy.

### 4. Deploy the frontend

Create a second service from the `./frontend` directory.

Set build-time variables:

```bash
NEXT_PUBLIC_API_URL=https://your-backend.up.railway.app
NEXT_PUBLIC_WORKSPACE_ID=default
```

Railway auto-detects Next.js and runs `npm install && npm run build && npm start`.

### 5. HTTPS

Railway provides HTTPS automatically on `*.up.railway.app` domains. For custom domains, add the domain in service settings and Railway provisions a certificate via Let's Encrypt.

### Pitfalls

- `DATABASE_URL` from Railway uses the `postgresql://` scheme. The backend needs `postgresql+asyncpg://`. Either use a variable reference and prepend the driver in the start command, or copy the URL and replace the scheme manually.
- `NEXT_PUBLIC_API_URL` is baked in at build time. If you change it, redeploy the frontend.

---

## Render

The repo ships `render.yaml` for blueprint deployment.

### 1. Fork and connect

1. Fork the repo on GitHub.
2. In the [Render dashboard](https://dashboard.render.com), click **New** → **Blueprint**.
3. Connect your GitHub fork. Render reads `render.yaml` and provisions backend, frontend, and a PostgreSQL 16 instance.

### 2. Set secrets

After the blueprint creates the services, go to **Environment** in the backend service and set:

```bash
JWT_SECRET=<generate with openssl rand -hex 32>
CORS_ORIGINS=["https://treco-frontend.onrender.com"]
ANTHROPIC_API_KEY=sk-ant-...   # optional
```

`JWT_SECRET` is marked `generateValue: true` in `render.yaml` — Render auto-generates it. Copy it from the dashboard if you need it elsewhere (e.g., for a staging environment that shares the same JWT audience).

`DATABASE_URL` is auto-wired from the managed database. `DATABASE_MODE=postgres` is set in the blueprint.

### 3. Custom domain

In the Render service settings, add a custom domain and point your DNS `CNAME` to the Render-provided hostname. Render provisions HTTPS automatically.

Update `CORS_ORIGINS` and `BACKEND_URL` / `FRONTEND_URL` to your custom domains after adding them.

### 4. HTTPS

Render terminates TLS automatically. No additional configuration is needed for `*.onrender.com` domains or custom domains.

### Pitfalls

- Render's free PostgreSQL plan expires after 90 days. Upgrade to a paid plan for production.
- The free web service tier spins down after 15 minutes of inactivity. The first request after a spin-down takes ~30 seconds. Use the Starter plan or add a cron job to keep the service warm.
- `NEXT_PUBLIC_API_URL` is set from `RENDER_EXTERNAL_URL` in `render.yaml` — this is the backend's Render URL. If you add a custom domain, override this variable manually in the frontend service.

---

## Fly.io

Fly.io deploys Docker containers globally. Use it if you want low-latency regional deploys or prefer Fly's pricing.

### 1. Install Fly CLI and authenticate

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

### 2. Provision a PostgreSQL cluster

```bash
fly postgres create --name treco-db --region iad
```

Note the connection string printed after creation. It uses the `postgres://` scheme — replace with `postgresql+asyncpg://` for the backend.

### 3. Deploy the backend

From the repo root:

```bash
cd backend
fly launch --name treco-backend --no-deploy
```

This creates `fly.toml`. Edit it:

```toml
[build]
  dockerfile = "Dockerfile"

[env]
  DATABASE_MODE = "postgres"
  PORT = "8001"

[[services]]
  internal_port = 8001
  protocol = "tcp"

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [services.http_checks]
    path = "/health"
    interval = "10s"
    timeout = "5s"
    grace_period = "30s"
```

Set secrets (not in `fly.toml` — Fly encrypts these separately):

```bash
fly secrets set \
  JWT_SECRET=$(openssl rand -hex 32) \
  DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@treco-db.internal:5432/treco \
  CORS_ORIGINS='["https://treco-frontend.fly.dev"]' \
  BACKEND_URL=https://treco-backend.fly.dev \
  FRONTEND_URL=https://treco-frontend.fly.dev \
  ANTHROPIC_API_KEY=sk-ant-...
```

Deploy:

```bash
fly deploy
```

Migrations run automatically via `entrypoint.sh` (`alembic upgrade head`) on every deploy.

### 4. Deploy the frontend

```bash
cd ../frontend
fly launch --name treco-frontend --no-deploy
```

Edit the generated `fly.toml` to pass build args:

```toml
[build]
  dockerfile = "Dockerfile"

[build.args]
  NEXT_PUBLIC_API_URL = "https://treco-backend.fly.dev"
  NEXT_PUBLIC_WORKSPACE_ID = "default"
```

```bash
fly deploy
```

### 5. HTTPS

Fly terminates TLS automatically on `*.fly.dev` domains. For custom domains:

```bash
fly certs create your-domain.com
```

Fly provisions a Let's Encrypt certificate and prints the DNS records to add.

### 6. Private networking

Fly services on the same organization can communicate over the private `6PN` network using `.internal` addresses. Use `treco-db.internal` in `DATABASE_URL` instead of the public IP to avoid egress fees.

### Pitfalls

- Fly's Postgres cluster is a separate app, not a managed service. You are responsible for backups. Use `fly postgres backup list` to verify backups are running.
- Build args (`NEXT_PUBLIC_*`) are baked at image build time. A `fly secrets set` on the frontend won't update them — you must add them to `[build.args]` in `fly.toml` and redeploy.
- `DATABASE_URL` must use `postgresql+asyncpg://`, not `postgres://` (which is what Fly prints after provisioning).

---

## Bare VPS with systemd

This setup runs the backend and frontend as systemd services on any Ubuntu/Debian VPS. It assumes:

- Ubuntu 22.04 or later
- A non-root user with `sudo`
- A domain pointed at the server's public IP
- Nginx for TLS termination

### 1. Install dependencies

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm postgresql nginx certbot python3-certbot-nginx
```

### 2. Create a PostgreSQL database

```bash
sudo -u postgres psql <<SQL
CREATE USER treco WITH PASSWORD 'a-strong-password';
CREATE DATABASE treco OWNER treco;
SQL
```

### 3. Clone and install the backend

```bash
sudo useradd -r -s /bin/false treco
sudo mkdir -p /opt/treco/backend
sudo chown treco:treco /opt/treco

git clone https://github.com/your-org/treco /opt/treco
cd /opt/treco/backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create `/opt/treco/backend/.env`:

```bash
JWT_SECRET=<openssl rand -hex 32>
DATABASE_URL=postgresql+asyncpg://treco:a-strong-password@localhost:5432/treco
DATABASE_MODE=postgres
CORS_ORIGINS=["https://treco.yourdomain.com"]
BACKEND_URL=https://api.yourdomain.com
FRONTEND_URL=https://treco.yourdomain.com
ANTHROPIC_API_KEY=sk-ant-...
```

```bash
chmod 600 /opt/treco/backend/.env
sudo chown treco:treco /opt/treco/backend/.env
```

Run migrations:

```bash
cd /opt/treco/backend
sudo -u treco .venv/bin/alembic upgrade head
```

### 4. Create the backend systemd unit

`/etc/systemd/system/treco-backend.service`:

```ini
[Unit]
Description=Treco Backend
After=network.target postgresql.service

[Service]
Type=simple
User=treco
WorkingDirectory=/opt/treco/backend
EnvironmentFile=/opt/treco/backend/.env
ExecStart=/opt/treco/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now treco-backend
```

### 5. Build and install the frontend

```bash
cd /opt/treco/frontend
npm install
NEXT_PUBLIC_API_URL=https://api.yourdomain.com \
NEXT_PUBLIC_WORKSPACE_ID=default \
npm run build
```

`/etc/systemd/system/treco-frontend.service`:

```ini
[Unit]
Description=Treco Frontend
After=network.target

[Service]
Type=simple
User=treco
WorkingDirectory=/opt/treco/frontend
Environment=PORT=3000
ExecStart=/usr/bin/npm start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now treco-frontend
```

### 6. Configure Nginx

`/etc/nginx/sites-available/treco`:

```nginx
server {
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    server_name treco.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/treco /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Provision TLS with Certbot

```bash
sudo certbot --nginx -d api.yourdomain.com -d treco.yourdomain.com
```

Certbot updates the Nginx config and installs a cron job to auto-renew certificates.

### 8. Updating Treco

```bash
cd /opt/treco
git pull

# Backend
cd backend
sudo -u treco .venv/bin/pip install -r requirements.txt
sudo -u treco .venv/bin/alembic upgrade head
sudo systemctl restart treco-backend

# Frontend (rebuild bakes in NEXT_PUBLIC_* at build time)
cd ../frontend
npm install
NEXT_PUBLIC_API_URL=https://api.yourdomain.com \
NEXT_PUBLIC_WORKSPACE_ID=default \
npm run build
sudo systemctl restart treco-frontend
```

### Pitfalls

- Bind the backend to `127.0.0.1`, not `0.0.0.0`, so it's only reachable via Nginx. Direct port exposure bypasses TLS.
- `NEXT_PUBLIC_API_URL` is baked at build time. Running `npm run build` with the wrong value means the dashboard calls the wrong API endpoint — rebuild after changing it.
- PostgreSQL's `asyncpg` driver requires Python 3.9+. Python 3.11 is recommended.
- The `EnvironmentFile` in the systemd unit is read as key=value pairs. Quoting rules differ from shell: `CORS_ORIGINS=["https://..."]` must not be shell-quoted. Write the JSON value literally.

---

## Common Pitfalls

### `asyncpg` vs `psycopg2`

`DATABASE_URL` must use `postgresql+asyncpg://`. The synchronous `psycopg2` driver raises `MissingGreenlet` errors at runtime because the backend uses an async SQLAlchemy engine. Many managed databases print a connection string with `postgres://` or `postgresql://` — prepend `+asyncpg` to the scheme.

### `JWT_SECRET` default in production

The default value `dev-secret-change-in-production` is a known string. Any JWT signed with it can be forged. The backend logs a warning if it detects the default, but the server still starts. Always generate a fresh secret:

```bash
openssl rand -hex 32
```

### `DATABASE_MODE=postgres` is required

Setting `DATABASE_URL` to a PostgreSQL URL is not enough. The codebase uses `DATABASE_MODE` to select the JSONB vs JSON column type. If `DATABASE_MODE` stays `sqlite` while `DATABASE_URL` points to Postgres, JSONB columns will use the wrong SQLAlchemy type and may fail at query time.

### `CORS_ORIGINS` must include the exact frontend origin

The value is a JSON list. The backend compares `Origin` headers exactly — no wildcard expansion. A mismatch between the frontend URL and `CORS_ORIGINS` causes browsers to block all API calls with no error in the backend logs (CORS errors are silent server-side). Include both `https://` and `http://` variants only during development.

### `NEXT_PUBLIC_API_URL` is baked at build time

This variable is embedded into the Next.js bundle when `npm run build` runs. Changing it at runtime (e.g., via an environment variable in a container) has no effect. Always pass it as a build argument or environment variable before building.

### GitHub OAuth callback URL must match exactly

The callback URL registered in your GitHub OAuth app must match `BACKEND_URL + /auth/github/callback` exactly, including the scheme. A mismatch causes a silent redirect failure — GitHub redirects to the registered URL, not the one in the request.

### Migrations on every deploy

The backend runs `alembic upgrade head` on startup via `entrypoint.sh`. This is safe for zero-downtime deploys because Alembic skips already-applied migrations. Do not disable it.

---

## Related

- [Self-Hosting](self-hosting.md) — Docker Compose quickstart for local production
- [Security](security.md) — auth model, key storage, workspace isolation
- [CLI Reference](cli-reference.md) — `treco` CLI commands including `treco init` for workspace setup

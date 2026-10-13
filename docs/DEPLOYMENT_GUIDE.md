# FieldOps AI — Full-Stack Production Deployment Guide

**Target Architecture:**
- **Frontend:** Vercel (Single Page React + Vite + TypeScript)
- **Backend API:** Render Web Service (FastAPI + Python 3.12 + Uvicorn)
- **Database:** MongoDB Atlas (M0/M10 Dedicated or Shared Cluster)
- **Background Jobs / Caching:** Upstash Redis / Render Redis + Celery (Optional)
- **Source Control:** GitHub (`main` branch)

```
[ Browser / Client ]
        |
        | HTTPS
        v
[ Vercel CDN Edge ] (Single Page React App)
        |
        | HTTPS (VITE_API_BASE_URL)
        v
[ Render Web Service ] (FastAPI Python 3.12)
        |
        +---> [ MongoDB Atlas ] (TLS / SRV Connection Pool)
        |
        +---> [ Redis / Celery ] (Transactional Outbox / Tasks)
```

---

## 1. Prerequisites

Before beginning deployment, ensure you have:
1. A **GitHub** account with this repository pushed to a private or public repository.
2. A **MongoDB Atlas** account ([mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)).
3. A **Render** account ([render.com](https://render.com)).
4. A **Vercel** account ([vercel.com](https://vercel.com)).

---

## 2. Step 1: Provision MongoDB Atlas Database

1. **Log in to MongoDB Atlas** and create a new project (e.g. `FieldOps-Production`).
2. **Deploy a Database Cluster:**
   - Select **M0 (Free)** or **M10 Dedicated** tier.
   - Select a cloud provider and region close to your backend (e.g., **AWS us-east-1 / Ohio** to match Render's Ohio region).
3. **Configure Database Access (User Credentials):**
   - In Atlas left navigation, go to **Security** $\rightarrow$ **Database Access**.
   - Click **Add New Database User**.
   - Authentication Method: **Password**.
   - Username: `fieldops_admin`
   - Password: Click **Autogenerate Secure Password** (save this securely).
   - Database User Privileges: `Read and write to any database` (or restrict to `fieldops_prod`).
   - Click **Add User**.
4. **Configure Network Access (Firewall):**
   - In Atlas left navigation, go to **Security** $\rightarrow$ **Network Access**.
   - Click **Add IP Address**.
   - To allow Render dynamic outbound IPs, enter `0.0.0.0/0` (Allow Access from Anywhere) with a comment `Render Web Service`.
   - Click **Confirm**.
5. **Obtain Connection String:**
   - Under **Deployments** $\rightarrow$ **Database**, click **Connect**.
   - Choose **Drivers** (Python / Motor).
   - Copy the SRV URI, which looks like:
     ```
     mongodb+srv://fieldops_admin:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=FieldOpsCluster
     ```
   - Replace `<password>` with your database user password. Note: If your password contains special characters (`@`, `:`, `/`, `#`), ensure they are URL-encoded.

---

## 3. Step 2: Deploy Backend to Render

### Option A: Using the Render Blueprint (`render.yaml` — Recommended)

The repository includes a root [`render.yaml`](file:///d:/FDE-PROJECTS/fieldops-ai/render.yaml) file specifying the build and start commands, health checks, and environment defaults.

1. Log in to the **Render Dashboard**.
2. Click **New +** $\rightarrow$ **Blueprint**.
3. Connect your GitHub repository (`fieldops-ai`).
4. Render will parse `render.yaml` and discover the `fieldops-api` web service.
5. Provide the two required manual sync environment variables when prompted:
   - `MONGODB_URL`: Paste your full MongoDB Atlas connection string.
   - `CORS_ORIGINS`: Set to `*` temporarily or your expected Vercel URL (e.g., `https://fieldops-ai.vercel.app`).
6. Click **Apply Blueprint**.

---

### Option B: Manual Web Service Setup via Dashboard

If deploying manually without the blueprint:

1. In Render Dashboard, click **New +** $\rightarrow$ **Web Service**.
2. Connect your GitHub repository.
3. Configure service settings:
   - **Name:** `fieldops-api`
   - **Region:** `Ohio (US East)`
   - **Branch:** `main`
   - **Root Directory:** *(leave blank — repository root)*
   - **Runtime:** `Python`
   - **Build Command:**
     ```bash
     pip install --upgrade pip && pip install ".[dev]"
     ```
   - **Start Command:**
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type:** `Starter` (or `Free`)
4. **Health Check Path:**
   - Set **Health Check Path** to `/health/live` (or `/api/v1/health`).
5. **Environment Variables:**
   Add the following variables under the **Environment** tab:

| Variable Name | Production Value / Description | Example |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.12.0` | `3.12.0` |
| `ENVIRONMENT` | `production` | `production` |
| `DEBUG` | `false` | `false` |
| `API_V1_STR` | `/api/v1` | `/api/v1` |
| `MONGODB_URL` | MongoDB Atlas SRV URI with user/password | `mongodb+srv://admin:pass@cluster.mongodb.net/?retryWrites=true` |
| `MONGODB_DB_NAME` | `fieldops_prod` | `fieldops_prod` |
| `MONGODB_MIN_POOL_SIZE` | `10` | `10` |
| `MONGODB_MAX_POOL_SIZE` | `50` | `50` |
| `MONGODB_SERVER_SELECTION_TIMEOUT_MS`| `5000` | `5000` |
| `JWT_SECRET_KEY` | Secure 64-character random string | *(Generate via `openssl rand -hex 32`)* |
| `JWT_ALGORITHM` | `HS256` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24 hours) | `1440` |
| `CORS_ORIGINS` | Deployed Vercel frontend domain | `["https://fieldops-ai.vercel.app"]` |
| `NOTIFICATION_PROVIDER` | `mock` (or `twilio`) | `mock` |
| `MAPS_PROVIDER` | `mock` (or `google`) | `mock` |
| `CALENDAR_PROVIDER` | `mock` | `mock` |
| `CRM_PROVIDER` | `mock` | `mock` |
| `VOICE_STT_PROVIDER` | `mock` | `mock` |
| `VOICE_TTS_PROVIDER` | `mock` | `mock` |
| `LLM_PROVIDER` | `mock` (or `openai`) | `mock` |
| `LOG_FORMAT` | `json` | `json` |
| `RATE_LIMIT_ENABLED` | `true` | `true` |
| `RATE_LIMIT_PER_MINUTE` | `120` | `120` |
| `SEED_ADMIN_EMAIL` | `admin@fieldops.ai` | `admin@fieldops.ai` |
| `SEED_ADMIN_PASSWORD` | Strong password for demo administrator | `AdminSecurePass2026!` |

6. Click **Create Web Service**.
7. Wait for deployment to complete. Note your assigned Render URL (e.g., `https://fieldops-api.onrender.com`).
8. Verify health by opening `https://YOUR-RENDER-URL/health/live` and `https://YOUR-RENDER-URL/health/ready` in your browser.

---

## 4. Step 3: Deploy Frontend to Vercel

1. Log in to **Vercel** ([vercel.com](https://vercel.com)).
2. Click **Add New...** $\rightarrow$ **Project**.
3. Import your GitHub repository (`fieldops-ai`).
4. In the Project Configuration screen:
   - **Framework Preset:** `Vite` (automatically detected).
   - **Root Directory:** Click **Edit** and select `frontend`.
   - **Build Command:** `npm run build` (or `tsc && vite build`).
   - **Output Directory:** `dist`.
   - **Install Command:** `npm install`.
5. **Environment Variables:**
   - Expand the **Environment Variables** section.
   - Add:
     - **Key:** `VITE_API_BASE_URL`
     - **Value:** `https://YOUR-RENDER-BACKEND-URL` (e.g., `https://fieldops-api.onrender.com`).
6. Click **Deploy**.
7. Vercel will install dependencies, compile TypeScript, bundle static assets, and assign a production URL (e.g., `https://fieldops-ai.vercel.app`).
8. **Update Backend CORS:**
   - Return to Render $\rightarrow$ `fieldops-api` $\rightarrow$ **Environment**.
   - Update `CORS_ORIGINS` to include your new Vercel URL:
     ```json
     ["https://fieldops-ai.vercel.app"]
     ```
   - Render will automatically trigger a zero-downtime redeploy.

---

## 5. Health Check & Verification URLs

Once deployed, verify both layers:

| Layer | URL Endpoint | Expected Response |
| :--- | :--- | :--- |
| **Backend Liveness** | `https://YOUR-BACKEND/health/live` | `{"status": "ok", "timestamp": "..."}` |
| **Backend Readiness** | `https://YOUR-BACKEND/health/ready` | `{"status": "ready", "database": "connected", "timestamp": "..."}` |
| **Operational Telemetry** | `https://YOUR-BACKEND/api/v1/metrics` | `{"status": "healthy", "service": "FieldOps AI", ...}` |
| **Frontend Homepage** | `https://YOUR-FRONTEND/` | HTTP 200 (Dashboard / Login view renders) |
| **Frontend Deep Route** | `https://YOUR-FRONTEND/dispatch` | HTTP 200 (SPA client-side rewrite renders without 404) |

---

## 6. Troubleshooting & Common Issues

### Issue 1: Backend Fails with `Database connection failed during startup`
- **Cause:** Network Access in MongoDB Atlas does not permit Render's outbound IP, or credentials have unescaped special characters.
- **Fix:** In MongoDB Atlas $\rightarrow$ Network Access, ensure `0.0.0.0/0` is active. If your database password contains characters like `@`, `%`, or `/`, URL-encode them.

### Issue 2: Frontend Shows CORS Error in Browser Console
- **Symptom:** `Access to fetch at 'https://fieldops-api...' has been blocked by CORS policy`.
- **Cause:** The Vercel URL is not listed in `CORS_ORIGINS` in Render.
- **Fix:** In Render Environment settings, update `CORS_ORIGINS` to `["https://your-vercel-domain.vercel.app"]` (ensure no trailing slash on the domain).

### Issue 3: Refreshing Deep Routes on Vercel Gives 404
- **Cause:** Static file server cannot find `/dispatch` or `/portal` on disk.
- **Fix:** Verified present: `frontend/vercel.json` contains a rewrite rule routing all paths to `/index.html`.

### Issue 4: Technician or Dispatcher Login Fails
- **Cause:** Database not seeded with demo accounts.
- **Fix:** Run the seed script against your Atlas database using:
  ```bash
  MONGODB_URL="your-atlas-url" python -m app.scripts.seed_data
  ```

---

## 7. Rollback Procedure

- **Render Rollback:** In Render Dashboard $\rightarrow$ **Deploys**, click on any previous healthy build and select **Rollback to this deploy**.
- **Vercel Rollback:** In Vercel Dashboard $\rightarrow$ **Deployments**, locate the last working deployment, click the three dots (`...`), and select **Instant Rollback**.


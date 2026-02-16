# CCVC Platform (React + Python API)

This project separates CCVC responsibilities:
- `frontend/` React visualization and analysis UI.
- `backend/` FastAPI solver API (GCCVC, GRCCVC, GWCCVC, HGA-CCVC, Exact B&B).

## Run with Docker Compose

```bash
docker compose up -d --build
```

This setup is intended for domain routing through the existing Caddy network (`webpage_default`).
Primary access:
- `https://ccvc.erberk.cloud`
- API health: `https://ccvc.erberk.cloud/api/health`

If you want a direct host port for local debugging:

```bash
CCVC_PORT=8090 docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

## Domain (`ccvc.erberk.cloud`)

This deployment expects a host-level Caddy/Nginx reverse proxy.
Current Caddy route target:
- `ccvc.erberk.cloud` -> `ccvc-frontend:80`

If you are configuring Nginx instead, example:

```nginx
server {
    listen 80;
    server_name ccvc.erberk.cloud;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then enable TLS (Let's Encrypt) at the reverse proxy layer.

## Local development (without Docker)

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000` in dev mode.

## Capacity K Modes

`/api/solve` now supports both manual and automatic K selection:

- Manual mode: send `capacityK` and `optimizeK: false`.
- Auto mode: send `optimizeK: true` and optional `optimizeGoal`:
  - `min-feasible-k`: binary search for smallest feasible K.
  - `best-weight`: binary search + scan for best objective weight.

The backend computes theoretical bounds from the input graph:

- `Kmin = ceil(|E| / |V|)` (necessary lower bound from total capacity),
- `Kmax = Δ(G)` (maximum degree, practical upper bound).

The response `meta` includes `kBounds` and `optimization` trial details.

## Dagdeviren Analysis Integration

CCVC now includes non-simulator analysis tooling inspired by `netos-independent-set`:

- `backend/app/analysis_tools/datareader.py`
- `backend/app/analysis_tools/GraphAnalyzer.py`
- `backend/app/analysis_tools/ScaleAnalyzer.py`
- `backend/app/analysis_tools/ConnectivityRatioVisualizer.py`
- `backend/app/analysis_tools/ScaleVisualizer.py`

API endpoints:

- `GET /api/analysis/dagdeviren/files`
- `GET /api/analysis/dagdeviren/ratios`
- `POST /api/analysis/dagdeviren/run`

Default dataset directory:

- `backend/data/DagdevirenDataset`

The repository includes a small sample file (`n10_m20_s1.txt`) and you can copy the full Dagdeviren dataset into that folder.

`POST /api/analysis/dagdeviren/run` also supports script-style configuration:

- `ratios` (like `discover_ratios(...)` output),
- `smallScales`, `mediumScales`, `largeScales`,
- `capacityByScale` (e.g. `{"small":18,"medium":16,"large":16}`).

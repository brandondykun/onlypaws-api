# SigNoz Observability Stack

Self-hosted [SigNoz](https://signoz.io/) providing traces, logs, and metrics for the OnlyPaws API.

## Architecture

The SigNoz stack runs as a **separate Docker Compose project** from the main app. They communicate over a shared `observability` Docker network.

```
App Stack (scripts/run.sh)              SigNoz Stack (start-signoz.sh)
┌────────────────────────┐              ┌────────────────────────┐
│  Django (Daphne)       │──OTLP gRPC──▶│  OTEL Collector :4317  │
│  Celery workers (x3)   │              │  ClickHouse            │
│  PostgreSQL            │              │  ZooKeeper             │
│  Redis                 │              │  SigNoz App :3301      │
└────────────────────────┘              └────────────────────────┘
         └──── observability network ────────┘
```

**SigNoz UI:** http://localhost:3301 (first visit requires creating an admin account)

**Remote access:** The UI is bound to `127.0.0.1` so it's not exposed externally. To view a remote server's SigNoz UI from your local machine, forward the port over SSH:

```bash
ssh -L 3301:127.0.0.1:3301 your-user@your-server
```

Then open http://localhost:3301 in your local browser.

## Quick Start

```bash
# Start SigNoz (do this before starting the app)
docker/signoz/start-signoz.sh

# Start the app
scripts/run.sh dev

# Open SigNoz UI
open http://localhost:3301
```

## Scripts

| Script | Description |
|--------|-------------|
| `start-signoz.sh` | Creates the `observability` network and starts all SigNoz services |
| `stop-signoz.sh` | Stops SigNoz, preserves telemetry data |
| `stop-signoz.sh -v` | Stops SigNoz and **wipes all data** (ClickHouse, ZooKeeper, SigNoz DB) |

## Services

| Service | Image | Purpose |
|---------|-------|---------|
| `signoz_zookeeper` | `signoz/zookeeper:3.7.1` | Coordination for ClickHouse Replicated tables |
| `signoz_clickhouse` | `clickhouse/clickhouse-server:25.5.6` | Time-series database for all telemetry data |
| `signoz_telemetrystore_migrator` | `signoz/signoz-otel-collector:v0.144.2` | Runs ClickHouse schema migrations on startup, then exits |
| `signoz_otel_collector` | `signoz/signoz-otel-collector:v0.144.2` | Receives OTLP data from app, writes to ClickHouse |
| `signoz_app` | `signoz/signoz:v0.116.1` | SigNoz UI and query API |
| `signoz_docker_collector` | `otel/opentelemetry-collector-contrib:0.139.0` | Collects host machine and Docker container metrics |

## Configuration Files

| File | Purpose |
|------|---------|
| `docker-compose.signoz.yml` | Service definitions, versions, networking |
| `collector-config.yaml` | OTEL Collector pipeline: receivers, processors, exporters |
| `clickhouse-cluster.xml` | ClickHouse listen address, ZooKeeper connection, cluster/shard/replica config |
| `clickhouse-users.xml` | ClickHouse default user (passwordless, all-network access) |
| `docker-collection-config.yaml` | Docker collection agent: host metrics, container stats |
| `docker-dashboard.json` | Pre-built SigNoz dashboard for container metrics (import via UI) |

## How Telemetry Flows

1. Django/Celery call `init_telemetry()` on startup (see `api/core/telemetry.py`)
2. OpenTelemetry SDK auto-instruments Django, psycopg2, Redis, Celery, and Python logging
3. Traces and logs are exported via gRPC to `signoz-otel-collector:4317`
4. The collector batches data, generates span metrics (RED metrics), and writes to ClickHouse
5. SigNoz App queries ClickHouse and renders the UI

**Telemetry is opt-in:** controlled by `OTEL_EXPORTER_OTLP_ENDPOINT` in the env file. If unset, `init_telemetry()` is a no-op and the app runs without any observability overhead.

## Independence

The two stacks are independent. Neither depends on the other to function.

| Scenario | App behavior | SigNoz behavior |
|----------|-------------|-----------------|
| App running, SigNoz stopped | App works normally. Telemetry exports fail silently. | N/A |
| SigNoz running, App stopped | N/A | SigNoz works. Historical data still viewable. |
| SigNoz restarted with `stop-signoz.sh` | App continues. Telemetry reconnects automatically. | Fresh start, data preserved. |
| SigNoz restarted with `stop-signoz.sh -v` | **Must recreate app containers** (see below). | Fresh start, data wiped. |

### After `stop-signoz.sh -v`

Wiping volumes destroys and recreates the `observability` network. App containers hold a reference to the old network and lose connectivity. Fix:

```bash
# Recreate app containers on the new network
cd docker && docker compose -f docker-compose.yml -f dev/docker-compose.override.yml up -d --force-recreate
```

## Docker Container Metrics Dashboard

The `signoz_docker_collector` service collects host machine metrics (CPU, memory, disk, network) and Docker container metrics (per-container CPU, memory, network I/O, block I/O) and sends them to SigNoz.

### Import the dashboard

1. Open SigNoz at http://localhost:3301
2. Go to **Dashboards** in the left sidebar
3. Click **+ New Dashboard** > **Import JSON**
4. Upload `docker/signoz/docker-dashboard.json`
5. The "Container Metrics" dashboard will appear with panels for CPU, memory, network, and I/O per container

### Metrics collected

| Source | Metrics |
|--------|---------|
| Host | `system.cpu.time`, `system.memory.usage`, `system.disk.io`, `system.network.io`, `system.filesystem.usage`, `system.processes.count` |
| Containers | `container.cpu.usage.total`, `container.memory.usage.total`, `container.network.io.usage.*`, `container.blockio.io_service_bytes_recursive` |

## Debugging

### Check service health

```bash
docker ps -a --filter "name=signoz" --format "table {{.Names}}\t{{.Status}}"
```

Expected: ZooKeeper and ClickHouse `healthy`, migrator `Exited (0)`, collector and app `Up`.

### Collector not starting

```bash
docker logs signoz_otel_collector 2>&1 | tail -20
```

Common causes:
- **ClickHouse not healthy yet** — collector depends on it, wait for ClickHouse healthcheck
- **Config error** — check `collector-config.yaml` syntax, look for "cannot unmarshal" in logs
- **DNS failure** — if collector can't resolve `clickhouse`, recreate: `docker compose -f docker-compose.signoz.yml up -d signoz-otel-collector`

### "Table is in readonly mode" errors

ZooKeeper and ClickHouse volumes are out of sync. This happens when one is wiped without the other (e.g., Docker Desktop restart wipes ZooKeeper but ClickHouse data persists).

```bash
# Fix: wipe both and start fresh
docker/signoz/stop-signoz.sh -v
docker/signoz/start-signoz.sh
```

### App can't reach collector (UNAVAILABLE errors)

```bash
# Check if collector is on the observability network
docker network inspect observability --format '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}' | grep signoz

# If missing, manually connect it
docker network connect observability signoz_otel_collector

# Then recreate app containers
cd docker && docker compose -f docker-compose.yml -f dev/docker-compose.override.yml up -d --force-recreate
```

### Logs not appearing in SigNoz UI

1. **Check traces first** — if traces work but logs don't, the issue is in log export, not networking
2. **Verify logs reach ClickHouse:**
   ```bash
   docker exec signoz_clickhouse clickhouse-client --query \
     "SELECT body FROM signoz_logs.distributed_logs_v2 WHERE timestamp > now() - INTERVAL 5 MINUTE ORDER BY timestamp DESC LIMIT 10"
   ```
3. **Verify the time range** in the SigNoz UI — expand to "Last 1 hour" if the default is too narrow

### Resource issues (DEADLINE_EXCEEDED)

ClickHouse needs adequate CPU/memory. Recommended Docker Desktop settings:
- **Memory:** 6 GB minimum (4 GB bare minimum)
- **CPUs:** 4 (3 minimum)

Check current usage:
```bash
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep signoz
```

## Environment Variables

Set in `docker/dev/.env.dev.local` (and corresponding staging/prod env files):

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | _(unset)_ | Collector endpoint. Set to `http://signoz-otel-collector:4317` to enable. |
| `OTEL_SERVICE_NAME` | `onlypaws-api` | Service name shown in SigNoz UI |
| `OTEL_BSP_EXPORT_TIMEOUT` | `30000` | BatchSpanProcessor export timeout in ms |

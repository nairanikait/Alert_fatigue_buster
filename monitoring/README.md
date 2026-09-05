# Prometheus & Blackbox Exporter Monitoring Architecture

This directory contains the production-ready monitoring and alerting stack configured to monitor the live public target **https://www.vendit.co.in/** using **Prometheus**, **Alertmanager**, and **Blackbox Exporter**, seamlessly integrated with the Alert Buster intelligence backend.

---

## Architecture Overview

```
                          [ Internet / Public Target ]
                           https://www.vendit.co.in/
                                      ▲
                                      │ HTTP Probe (200 OK check, timeout 5s)
                                      │
+------------------------- Blackbox Exporter (Port 9115) -------------------------+
| - Executes http_2xx probe module against https://www.vendit.co.in/              |
| - Measures probe_success (1 = success, 0 = failure), latency, DNS, SSL certs    |
+---------------------------------------------------------------------------------+
                                      ▲
                                      │ Scrapes /probe?module=http_2xx
                                      │ Scrape Interval: 15s | Eval Interval: 10s
+--------------------------- Prometheus (Port 9090) ------------------------------+
| - Evaluates Alert Rule: ProjectDown (probe_success == 0 for 10s)                |
| - Forwards firing alerts to Alertmanager                                        |
+---------------------------------------------------------------------------------+
                                      ▲
                                      │ Webhook payload (JSON)
                                      │
+-------------------------- Alertmanager (Port 9093) -----------------------------+
| - Groups alerts and manages resolve timeouts                                    |
| - Dispatches to webhook: http://backend:8000/api/alerts/prometheus             |
| - Sends resolution events (send_resolved: true)                                 |
+---------------------------------------------------------------------------------+
                                      ▲
                                      │ POST /api/alerts/prometheus
                                      │
+------------------------ Alert Buster Backend (Port 8000) -----------------------+
| - Deduplicates bursts into single incident fingerprint                          |
| - Calculates 0-100 severity score                                               |
| - Correlates downstream blast radius                                            |
| - Dispatches actionable on-call notification to PagerDuty / Slack               |
| - Updates WebSocket stream for React Dashboard                                  |
+---------------------------------------------------------------------------------+
```

---

## How Each Component Works

### 1. Blackbox Exporter (`monitoring/blackbox.yml`)
- Operates on port `9115`.
- Configured with the `http_2xx` module.
- Sends actual HTTP GET requests to `https://www.vendit.co.in/` with:
  - `timeout: 5s`
  - `valid_status_codes: [200]`
  - `follow_redirects: true`
- If `https://www.vendit.co.in/` returns HTTP 200, Blackbox exposes `probe_success = 1`. If the endpoint times out, returns 4xx/5xx, or DNS fails, it sets `probe_success = 0`.

### 2. Prometheus (`monitoring/prometheus.yml`)
- Operates on port `9090`.
- Scrapes the Blackbox Exporter at `/probe` every `15s` passing `params: { module: [http_2xx] }` and `target: https://www.vendit.co.in/`.
- Uses Prometheus relabeling to preserve `instance="https://www.vendit.co.in/"` on the resulting time-series metrics.
- Continuously evaluates `monitoring/rules.yml` every `10s`.

### 3. Alert Rule (`monitoring/rules.yml`)
- **Alert Name:** `ProjectDown`
- **Expression:** `probe_success == 0`
- **Duration:** `for: 10s`
- **Labels:** `severity: critical`, `service: vendit-app`, `environment: production`
- **Annotations:** `summary: "Project target endpoint is unreachable: {{ $labels.instance }}"`

### 4. Alertmanager (`monitoring/alertmanager.yml`)
- Operates on port `9093`.
- Receives firing `ProjectDown` alerts from Prometheus.
- Configured with a single webhook receiver pointing to:
  `http://backend:8000/api/alerts/prometheus`
- Has `send_resolved: true` enabled so when the target recovers and `probe_success` returns to 1, Alertmanager transmits a resolution payload (`status: "resolved"` with `endsAt`) to transition the backend incident to `RESOLVED`.

### 5. Alert Buster Backend (`backend/app/api/alerts.py`)
- Ingests the standard Prometheus Alertmanager JSON payload at `POST /api/alerts/prometheus`.
- Normalizes the payload in `backend/app/services/normalization.py`.
- Enters `process_alert()` pipeline:
  1. Computes SHA-256 fingerprint from `ProjectDown|vendit-app|none|production`.
  2. Evaluates severity score (80+ Critical).
  3. Correlates into active incident cluster.
  4. Dispatches notification to PagerDuty/Slack adapter.
  5. Broadcasts real-time WebSocket update to React UI.

---

## How to Verify and Check the Monitoring Stack

When the Docker Compose stack is running (`docker compose up -d`):

### 1. Check Prometheus Targets
Open: **http://localhost:9090/targets**
- Verify that `blackbox-http` shows state `UP (1/1)`.
- Click on the target URL to view live probe metrics.

### 2. Check Prometheus Metrics (`probe_success`)
Open: **http://localhost:9090/graph**
- In the query bar, type: `probe_success` and click **Execute**.
- Value `1` indicates `https://www.vendit.co.in/` is healthy and returning HTTP 200.
- Check additional metrics:
  - `probe_duration_seconds` (HTTP response latency)
  - `probe_http_status_code` (e.g. 200)
  - `probe_ssl_earliest_cert_expiry` (SSL expiration)

### 3. Check Prometheus Active Alert Rules
Open: **http://localhost:9090/alerts**
- Locate rule `ProjectDown`.
- State will be `Inactive` (green) when `probe_success == 1`.
- State transitions to `Pending` (amber for 10s) and then `Firing` (red) if `probe_success == 0`.

### 4. Check Alertmanager UI
Open: **http://localhost:9093**
- Displays all currently active alerts dispatched from Prometheus.
- Shows alert group status and receiver delivery status.

---

## How to Test a Real `ProjectDown` Alert

Because **https://www.vendit.co.in/** is an external public production deployment, do **not** attempt to modify or stop the external target. Instead, use any of the standard validation techniques:

### Method A: End-to-End Simulation via Backend Ingestion
Send a simulated Alertmanager payload directly to the backend webhook endpoint:
```bash
curl -X POST http://localhost:8000/api/alerts/prometheus \
  -H "Content-Type: application/json" \
  -d '{
    "version": "4",
    "status": "firing",
    "receiver": "alert_buster_backend",
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "ProjectDown",
          "service": "vendit-app",
          "severity": "critical",
          "instance": "https://www.vendit.co.in/"
        },
        "annotations": {
          "summary": "Project target endpoint is unreachable: https://www.vendit.co.in/",
          "description": "Blackbox prober reported probe_success == 0 for https://www.vendit.co.in/"
        },
        "startsAt": "2026-09-04T18:45:00Z",
        "fingerprint": "vendit_probe_fp_01"
      }
    ]
  }'
```
Inspect the Alert Buster Dashboard (**http://localhost:5173**) to observe the critical alert, incident creation, and PagerDuty dispatch notification.

To simulate recovery:
```bash
curl -X POST http://localhost:8000/api/alerts/prometheus \
  -H "Content-Type: application/json" \
  -d '{
    "version": "4",
    "status": "resolved",
    "receiver": "alert_buster_backend",
    "alerts": [
      {
        "status": "resolved",
        "labels": {
          "alertname": "ProjectDown",
          "service": "vendit-app",
          "severity": "critical",
          "instance": "https://www.vendit.co.in/"
        },
        "annotations": {
          "summary": "Project target endpoint is unreachable: https://www.vendit.co.in/"
        },
        "startsAt": "2026-09-04T18:45:00Z",
        "endsAt": "2026-09-04T18:48:00Z",
        "fingerprint": "vendit_probe_fp_01"
      }
    ]
  }'
```

### Method B: Live Probe Failure Test via Temporary Unreachable Target
1. In `monitoring/prometheus.yml`, temporarily add an unreachable target (e.g. `https://www.vendit.co.in.invalid-test-domain/` or `https://httpstat.us/500`).
2. Reload Prometheus: `docker compose exec prometheus kill -HUP 1` or restart Prometheus container.
3. Observe `probe_success` drop to `0` in `http://localhost:9090/graph`.
4. After 10 seconds, watch `ProjectDown` transition to **Firing** in `http://localhost:9090/alerts`.
5. Check `http://localhost:9093` to see Alertmanager dispatch the webhook to `http://backend:8000/api/alerts/prometheus`.
6. Verify the incident appears in Alert Buster Web UI (**http://localhost:5173**).
7. Revert target back to `https://www.vendit.co.in/` and watch Alertmanager send `status: "resolved"`.

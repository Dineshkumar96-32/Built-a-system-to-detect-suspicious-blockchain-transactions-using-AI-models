# BlockShield API Reference

Base URL: `https://your-host/api/v1`

All endpoints (except `/auth/token` and `/health`) require either:
- `Authorization: Bearer <jwt_access_token>`, **or**
- `x-api-key: <static_api_key>` (legacy)

---

## Authentication

### `POST /auth/token`
Exchange credentials for a JWT token pair.

**Body** (`application/x-www-form-urlencoded`)
```
username=analyst@example.com&password=secret&grant_type=password
```

**Response 200**
```json
{
  "access_token":  "eyJ...",
  "refresh_token": "eyJ...",
  "token_type":    "bearer",
  "expires_in":    1800
}
```

---

### `POST /auth/refresh`
Exchange a refresh token for a new token pair.

**Body** (`application/json`)
```json
{ "refresh_token": "eyJ..." }
```

---

### `GET /auth/me`
Returns the authenticated user's profile.

**Response 200**
```json
{ "sub": "analyst@example.com", "role": "analyst", "scopes": ["transactions:read","feedback:write"] }
```

---

## Transactions

### `GET /transactions`
Paginated list of ingested transactions with optional filters.

**Query params**

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `size` | int | 50 | Page size (max 200) |
| `chain` | str | — | Filter by chain (`ethereum`, `polygon`, …) |
| `min_score` | float | — | Min anomaly score `[0,1]` |
| `wallet` | str | — | Filter by wallet address |
| `from_ts` | ISO8601 | — | Start timestamp |
| `to_ts` | ISO8601 | — | End timestamp |
| `flagged` | bool | — | Only anomalous txs |

**Response 200**
```json
{
  "total": 1042,
  "page": 1,
  "size": 50,
  "items": [
    {
      "tx_hash":       "0xabc...",
      "chain":         "ethereum",
      "block_number":  19800000,
      "from":          "0xsender...",
      "to":            "0xreceiver...",
      "value_eth":     1.5,
      "gas_price_gwei":42.1,
      "anomaly_score": 0.83,
      "gnn_risk_score":0.76,
      "flagged":       true,
      "timestamp":     "2025-05-01T12:00:00Z"
    }
  ]
}
```

---

### `GET /transactions/{tx_hash}`
Full detail for a single transaction including feature vector.

---

### `GET /transactions/stream`
Server-Sent Events stream of live transactions.

**Headers:** `Accept: text/event-stream`

Each event:
```
data: {"tx_hash":"0x...","anomaly_score":0.91,...}
```

---

## Wallet

### `GET /wallet/{address}/risk`
Compute or retrieve cached risk profile for a wallet.

**Response 200**
```json
{
  "address":          "0xabc...",
  "anomaly_score":    0.74,
  "gnn_risk_score":   0.81,
  "ofac_flagged":     false,
  "mixer_interaction":true,
  "out_degree":       42,
  "in_degree":        7,
  "tx_count_24h":     18,
  "counterparty_entropy": 1.23,
  "community_id":     5,
  "cluster_size":     14,
  "risk_tier":        "HIGH",
  "last_seen":        "2025-05-01T11:55:00Z"
}
```

---

### `GET /wallet/{address}/cluster`
Returns the community cluster this wallet belongs to — all related wallets and their edges.

**Response 200**
```json
{
  "community_id": 5,
  "nodes": [
    { "address": "0xabc...", "risk_tier": "HIGH", "gnn_risk_score": 0.81 }
  ],
  "edges": [
    { "from": "0xabc...", "to": "0xdef...", "tx_count": 3, "total_eth": 4.2 }
  ]
}
```

---

### `GET /wallet/{address}/timeline`
Chronological transaction history for a wallet with computed features per tx.

**Query params:** `limit` (default 100), `from_ts`, `to_ts`

---

## Alerts

### `GET /alerts`
List alerts with optional status filter.

**Query params:** `status` (`open|assigned|closed`), `severity`, `page`, `size`

---

### `POST /alerts/{alert_id}/assign`
Assign an alert to an analyst.

**Body**
```json
{ "analyst_id": "analyst@example.com" }
```

---

### `POST /alerts/{alert_id}/comment`
Add a comment to an alert thread.

**Body**
```json
{ "text": "Confirmed wash trading pattern — related to cluster #5." }
```

---

### `POST /alerts/{alert_id}/close`
Close an alert with a resolution note.

**Body**
```json
{ "resolution": "false_positive", "note": "Verified legitimate DEX arbitrage." }
```

**Resolution values:** `confirmed_fraud | false_positive | escalated | monitoring`

---

## Alert Rules

### `GET /rules`
List all alert rules (active and inactive).

### `POST /rules`
Create a new rule. Body is an `AlertRule` JSON object from `AlertRuleBuilder.tsx`.

### `PUT /rules/{rule_id}`
Update an existing rule.

### `DELETE /rules/{rule_id}`
Delete a rule. Requires `admin:all` scope.

### `POST /rules/{rule_id}/toggle`
Toggle `active` state without a full PUT.

---

## Analyst Feedback

### `POST /feedback`
Submit an analyst label for a transaction.

**Body**
```json
{
  "tx_hash":        "0xabc...",
  "wallet_address": "0xsender...",
  "label":          1,
  "analyst_id":     "analyst@example.com",
  "features":       { "anomaly_score": 0.83, "gas_price_gwei": 42.1 }
}
```

**Response 200**
```json
{ "status": "accepted", "pending": 23, "retrain_threshold": 50 }
```

---

### `GET /feedback/stats`
Returns feedback queue depth and retrain status.

---

## Analytics

### `GET /analytics/heatmap`
Transaction volume/risk heatmap by hour-of-day × day-of-week.

**Query params:** `chain`, `from_ts`, `to_ts`, `metric` (`volume|anomaly_rate|tx_count`)

**Response 200**
```json
{
  "metric": "anomaly_rate",
  "cells": [
    { "day": 0, "hour": 14, "value": 0.12 }
  ]
}
```

---

### `GET /analytics/trend`
Daily aggregated time-series for key metrics.

**Query params:** `metric` (`tx_count|anomaly_rate|flagged_wallets|avg_score`), `days` (default 30)

---

### `GET /analytics/model`
Current model version, contamination, training rows, last retrain timestamp.

---

## System

### `GET /health`
Liveness probe. Returns `200 OK` with `{"status":"ok"}`.

### `GET /metrics`
Prometheus scrape endpoint (`text/plain`).

---

## Error Responses

All errors follow RFC 7807:

```json
{
  "status":  403,
  "title":   "Forbidden",
  "detail":  "Insufficient permissions. Required scope: admin:all",
  "type":    "https://blockshield.io/errors/forbidden"
}
```

| Status | Meaning |
|---|---|
| 400 | Validation error |
| 401 | Missing / invalid token |
| 403 | Valid token but insufficient scope |
| 404 | Resource not found |
| 422 | Request body schema error |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

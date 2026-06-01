// src/services/api.ts
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_KEY = import.meta.env.VITE_API_KEY || ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 
      'Content-Type': 'application/json',
      'x-api-key': API_KEY
    },
    ...options,
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const api = {
  getTransactions: async (params?: { limit?: number; flagged_only?: boolean; min_risk?: number }) => {
    const backendParams: any = {}
    if (params) {
      if (params.limit !== undefined) backendParams.size = params.limit
      if (params.flagged_only !== undefined) backendParams.flagged = params.flagged_only
      if (params.min_risk !== undefined) backendParams.min_score = params.min_risk / 100
    }
    const q = new URLSearchParams(backendParams).toString()
    const res = await request<PaginatedResponse<Transaction>>(`/api/v1/transactions${q ? '?' + q : ''}`)
    return res.items || []
  },
  getTransaction: (hash: string) => request<Transaction>(`/api/v1/transactions/${hash}`),
  searchTransactions: (query: string) => request<Transaction[]>(`/api/v1/search?q=${encodeURIComponent(query)}`),
  getAlerts: async (params?: { limit?: number; severity?: string }) => {
    const backendParams: any = {}
    if (params) {
      if (params.limit !== undefined) backendParams.size = params.limit
      if (params.severity !== undefined) backendParams.severity = params.severity.toUpperCase()
    }
    const q = new URLSearchParams(backendParams).toString()
    const res = await request<PaginatedResponse<Alert>>(`/api/v1/alerts${q ? '?' + q : ''}`)
    return res.items || []
  },
  getMetrics: () => request<SystemMetrics>('/api/v1/metrics'),
  getWalletRisk: (address: string) => request<WalletProfile>(`/api/v1/wallet/${address}/risk`),
  getTopRiskWallets: () => request<WalletProfile[]>('/api/v1/wallets/top-risk'),
  getNetworkGraph: (limit?: number) => request<{ nodes: any[]; links: any[] }>(`/api/v1/wallets/graph${limit ? '?limit=' + limit : ''}`),
  getSettings: () => request<SettingsResponse>('/api/v1/settings'),
  updateSettings: (body: { webhook_enabled: boolean; webhook_url: string }) => 
    request<SettingsUpdateResponse>('/api/v1/settings', {
      method: 'POST',
      body: JSON.stringify(body)
    }),
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  total: number
  page: number
  size: number
  items: T[]
}

export interface SettingsResponse {
  webhook_enabled: boolean
  webhook_url: string
}

export interface SettingsUpdateResponse {
  status: string
  webhook_enabled: boolean
  webhook_url: string
}

export interface Transaction {
  hash: string
  block_number: number
  timestamp: string
  from_address: string
  to_address: string | null
  value_eth: number
  gas_price_gwei: number
  risk_score: number
  is_flagged: boolean
  fraud_type: string | null
  confidence: number
  signals: string[]
}

export interface Alert {
  id: string
  tx_hash: string
  alert_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  risk_score: number
  description: string
  wallet_address: string | null
  value_eth: number
  created_at: string
  resolved: boolean
}

export interface SystemMetrics {
  total_processed: number
  total_flagged: number
  total_alerts: number
  flash_loan_count: number
  high_value_count: number
  wallet_nodes: number
  wallet_edges: number
  precision: number
  recall: number
  false_positive_rate: number
  tx_per_second: number
  elapsed_seconds: number | null
}

export interface WalletProfile {
  address: string
  tx_count: number
  volume_eth: number
  risk_score: number
  cluster_id: number | null
  cluster_risk: number
  out_degree: number
  in_degree: number
  known: boolean
}

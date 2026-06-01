// src/store/index.ts
import { create } from 'zustand'
import type { Transaction, Alert, SystemMetrics } from '../services/api'

interface AppState {
  transactions: Transaction[]
  alerts: Alert[]
  metrics: SystemMetrics | null
  wsConnected: boolean
  selectedTx: Transaction | null
  setSelectedTx: (tx: Transaction | null) => void

  addTransaction: (tx: Transaction) => void
  addAlert: (alert: Alert) => void
  setMetrics: (m: SystemMetrics) => void
  setWsConnected: (v: boolean) => void
  resolveAlert: (id: string) => void
}

export const useStore = create<AppState>((set) => ({
  transactions: [],
  alerts: [],
  metrics: null,
  wsConnected: false,
  selectedTx: null,

  setSelectedTx: (selectedTx) => set({ selectedTx }),
  addTransaction: (tx) =>
    set((s) => {
      const exists = s.transactions.some((t) => t.hash === tx.hash)
      if (exists) return s
      return {
        transactions: [tx, ...s.transactions].slice(0, 500),
      }
    }),

  addAlert: (alert) =>
    set((s) => {
      // de-duplicate by id
      const exists = s.alerts.some((a) => a.id === alert.id)
      if (exists) return s
      return { alerts: [alert, ...s.alerts].slice(0, 200) }
    }),

  setMetrics: (metrics) => set({ metrics }),
  setWsConnected: (wsConnected) => set({ wsConnected }),

  resolveAlert: (id) =>
    set((s) => ({
      alerts: s.alerts.map((a) => (a.id === id ? { ...a, resolved: true } : a)),
    })),
}))

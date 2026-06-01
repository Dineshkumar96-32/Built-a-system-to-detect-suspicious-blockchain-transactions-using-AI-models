// src/pages/Alerts.tsx
import { useState, useEffect } from 'react'
import { api, Alert } from '../services/api'
import { useStore } from '../store'
import { RiskBadge } from '../components/RiskBadge'

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getAlerts({ limit: 100 }).then(setAlerts).finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono p-8">
      <div className="max-w-screen-xl mx-auto space-y-8">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Security Alerts</h1>
            <p className="text-gray-500 mt-1">Historical log of all flagged suspicious activity.</p>
          </div>
          <div className="bg-red-950/20 border border-red-900/50 rounded-lg px-4 py-2">
            <span className="text-red-400 font-bold">{alerts.length}</span>
            <span className="text-gray-500 ml-2 text-sm uppercase tracking-wider">Total Incidents</span>
          </div>
        </header>

        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-gray-950 border-b border-gray-800 text-[10px] uppercase tracking-widest font-bold text-gray-500">
                <th className="px-6 py-4">Timestamp</th>
                <th className="px-6 py-4">Severity</th>
                <th className="px-6 py-4">Type</th>
                <th className="px-6 py-4">Wallet / Tx</th>
                <th className="px-6 py-4">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {loading ? (
                <tr><td colSpan={5} className="px-6 py-12 text-center text-gray-600">Loading alerts...</td></tr>
              ) : alerts.length === 0 ? (
                <tr><td colSpan={5} className="px-6 py-12 text-center text-gray-600">No security incidents detected yet.</td></tr>
              ) : (
                alerts.map(alert => (
                  <tr key={alert.id} className="hover:bg-gray-800/30 transition-colors">
                    <td className="px-6 py-4 text-xs text-gray-400 whitespace-nowrap">
                      {new Date(alert.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      <RiskBadge score={alert.risk_score} />
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2 py-1 bg-gray-800 rounded text-[10px] font-bold uppercase tracking-wider text-orange-400 border border-orange-900/30">
                        {alert.alert_type.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-mono text-xs">
                      <div className="text-gray-300">{alert.wallet_address?.slice(0, 10)}...</div>
                      <div className="text-gray-600 mt-0.5">{alert.tx_hash.slice(0, 10)}...</div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-400">
                      {alert.description}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

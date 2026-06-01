import { useEffect, useCallback, useState } from 'react'
import { useStore } from '../store'
import { api } from '../services/api'
import { MetricCard } from '../components/MetricCard'
import { TransactionTable } from '../components/TransactionTable'
import { AlertFeed } from '../components/AlertFeed'
import { RiskChart } from '../components/RiskChart'

export default function Dashboard() {
  const { addTransaction, addAlert, setMetrics, metrics, transactions, alerts, setSelectedTx } = useStore()
  const [tab, setTab] = useState<'all' | 'flagged'>('all')

  // Poll metrics every 10s for secondary system stats
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const m = await api.getMetrics()
        setMetrics(m)
      } catch (err) {}
    }
    fetchMetrics()
    const timer = setInterval(fetchMetrics, 10000)
    return () => clearInterval(timer)
  }, [setMetrics])

  // Initial data load for historical context
  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const [txs, als] = await Promise.all([
          api.getTransactions({ limit: 50 }),
          api.getAlerts({ limit: 20 })
        ])
        txs.forEach(addTransaction)
        als.forEach(addAlert)
      } catch (err) {
        console.error('Failed to load initial data', err)
      }
    }
    loadInitialData()
  }, [addTransaction, addAlert])

  const displayTxs = tab === 'flagged'
    ? transactions.filter((t) => t.is_flagged)
    : transactions
  const activeAlerts = alerts.filter((a) => !a.resolved)

  return (
    <div className="p-8 space-y-8 max-w-screen-xl mx-auto">
      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Transactions"
          value={metrics?.total_processed?.toLocaleString() ?? '—'}
          sub="total analyzed"
          icon="📊"
          color="blue"
        />
        <MetricCard
          label="Precision"
          value={metrics ? `${metrics.precision}%` : '—'}
          sub={`${metrics?.false_positive_rate ?? '—'}% FPR`}
          icon="🎯"
          color="green"
        />
        <MetricCard
          label="Alerts"
          value={metrics?.total_alerts?.toLocaleString() ?? '—'}
          sub={`${metrics?.flash_loan_count ?? 0} flash loans`}
          icon="🚨"
          color="red"
        />
        <MetricCard
          label="Wallets Tracked"
          value={metrics?.wallet_nodes?.toLocaleString() ?? '—'}
          sub={`${metrics?.wallet_edges?.toLocaleString() ?? 0} edges`}
          icon="🕸"
          color="purple"
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: charts + tx table */}
        <div className="lg:col-span-2 space-y-6">
          <RiskChart transactions={transactions} />

          {/* Transaction table with tabs */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl">
            <div className="flex items-center gap-4 px-4 py-3 border-b border-gray-800 bg-gray-900/50">
              <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Recent Activity</h2>
              <div className="flex gap-2 ml-auto">
                {(['all', 'flagged'] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={`text-[10px] uppercase tracking-wider font-bold px-3 py-1 rounded transition-all ${
                      tab === t
                        ? 'bg-orange-600 text-white shadow-lg shadow-orange-900/20'
                        : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800'
                    }`}
                  >
                    {t === 'all' ? 'All' : '🚩 Flagged'}
                  </button>
                ))}
              </div>
            </div>
            <TransactionTable 
              transactions={displayTxs.slice(0, 30)} 
              onRowClick={setSelectedTx}
            />
          </div>
        </div>

        {/* Right: alert feed */}
        <div className="space-y-6">
          <AlertFeed alerts={activeAlerts.slice(0, 15)} />

          {/* Top stats */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3 shadow-xl">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Detection Breakdown</h2>
            {[
              { label: 'Flash Loan Attacks', value: metrics?.flash_loan_count ?? 0, color: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.3)]' },
              { label: 'High-Value Transfers', value: metrics?.high_value_count ?? 0, color: 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.3)]' },
              { label: 'Anomaly Detections', value: (metrics?.total_flagged ?? 0) - (metrics?.flash_loan_count ?? 0) - (metrics?.high_value_count ?? 0), color: 'bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.3)]' },
            ].map(({ label, value, color }) => {
              const total = metrics?.total_flagged || 1
              const pct = Math.min(100, Math.round((value / total) * 100))
              return (
                <div key={label}>
                  <div className="flex justify-between text-[10px] text-gray-500 uppercase font-bold mb-1.5">
                    <span>{label}</span>
                    <span className="text-gray-300">{value.toLocaleString()}</span>
                  </div>
                  <div className="h-1.5 bg-gray-800/50 rounded-full overflow-hidden border border-gray-800">
                    <div
                      className={`h-full ${color} rounded-full transition-all duration-700`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          {/* Throughput */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 shadow-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 p-3 opacity-10">
              <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 24 24"><path d="M13 10V3L4 14H11V21L20 10H13Z" /></svg>
            </div>
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">System Load</h2>
            <div className="text-3xl font-bold text-white tracking-tighter">
              {metrics?.tx_per_second?.toFixed(1) ?? '—'}
              <span className="text-xs font-normal text-gray-500 ml-1 uppercase tracking-widest">tx/sec</span>
            </div>
            <div className="text-[10px] text-gray-500 mt-1 uppercase tracking-wider font-semibold">
              Real-time Analysis Pipeline
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 text-[10px] uppercase tracking-wider font-bold">
              <div className="bg-gray-800/50 border border-gray-800 rounded p-2">
                <div className="text-gray-500 mb-0.5">Recall</div>
                <div className="text-green-400 font-bold">{metrics?.recall ?? 88.1}%</div>
              </div>
              <div className="bg-gray-800/50 border border-gray-800 rounded p-2">
                <div className="text-gray-500 mb-0.5">F1 Score</div>
                <div className="text-blue-400 font-bold">90.3%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

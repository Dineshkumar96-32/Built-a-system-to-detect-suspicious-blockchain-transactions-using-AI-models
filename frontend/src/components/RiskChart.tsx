// src/components/RiskChart.tsx
import { useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import type { Transaction } from '../services/api'

interface Props {
  transactions: Transaction[]
}

function bucketByTime(txs: Transaction[], buckets: number = 30) {
  if (txs.length === 0) return []

  const now = Date.now()
  const windowMs = 5 * 60 * 1000 // 5 minutes
  const bucketMs = windowMs / buckets
  const data: { t: string; avg: number; max: number; count: number }[] = []

  for (let i = buckets - 1; i >= 0; i--) {
    const tEnd = now - i * bucketMs
    const tStart = tEnd - bucketMs
    const bucket = txs.filter((tx) => {
      const ts = new Date(tx.timestamp).getTime()
      return ts >= tStart && ts < tEnd
    })
    const avg = bucket.length
      ? bucket.reduce((s, t) => s + t.risk_score, 0) / bucket.length
      : 0
    const max = bucket.length ? Math.max(...bucket.map((t) => t.risk_score)) : 0
    const label = new Date(tEnd).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    data.push({ t: label, avg: +avg.toFixed(1), max: +max.toFixed(1), count: bucket.length })
  }
  return data
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 text-xs font-mono shadow-xl">
      <div className="text-gray-400 mb-2">{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name}: <strong>{p.value}</strong>
        </div>
      ))}
    </div>
  )
}

export function RiskChart({ transactions }: Props) {
  const data = useMemo(() => bucketByTime(transactions), [transactions])

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-300">Risk Score — Live (5min window)</h2>
        <span className="text-xs text-gray-600">30-second buckets</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="gradMax" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradAvg" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="t"
            tick={{ fill: '#4b5563', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            interval={9}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: '#4b5563', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={65} stroke="#ef4444" strokeDasharray="4 4" strokeOpacity={0.5} />
          <Area
            type="monotone"
            dataKey="max"
            name="Max Risk"
            stroke="#ef4444"
            strokeWidth={1.5}
            fill="url(#gradMax)"
          />
          <Area
            type="monotone"
            dataKey="avg"
            name="Avg Risk"
            stroke="#f97316"
            strokeWidth={1.5}
            fill="url(#gradAvg)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// src/components/AlertFeed.tsx
import { useStore } from '../store'
import type { Alert } from '../services/api'

interface Props {
  alerts: Alert[]
}

const severityStyles: Record<string, string> = {
  critical: 'border-red-700 bg-red-950/40 text-red-400',
  high:     'border-orange-700 bg-orange-950/40 text-orange-400',
  medium:   'border-yellow-700 bg-yellow-950/30 text-yellow-400',
  low:      'border-gray-700 bg-gray-800/30 text-gray-400',
}

const severityIcons: Record<string, string> = {
  critical: '🔴',
  high:     '🟠',
  medium:   '🟡',
  low:      '🟢',
}

function timeAgo(dateStr: string): string {
  const secs = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (secs < 60) return `${secs}s ago`
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  return `${Math.floor(secs / 3600)}h ago`
}

export function AlertFeed({ alerts }: Props) {
  const resolveAlert = useStore((s) => s.resolveAlert)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <h2 className="text-sm font-semibold text-gray-300">Live Alerts</h2>
        {alerts.length > 0 && (
          <span className="text-xs bg-red-900/50 text-red-400 border border-red-800 rounded-full px-2 py-0.5">
            {alerts.length}
          </span>
        )}
      </div>

      <div className="divide-y divide-gray-800/50 max-h-[480px] overflow-y-auto">
        {alerts.length === 0 ? (
          <div className="py-12 text-center text-gray-600 text-sm">
            No active alerts
          </div>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              className={`p-3 border-l-2 ${severityStyles[alert.severity]} transition-all`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm">{severityIcons[alert.severity]}</span>
                  <span className="text-xs font-bold uppercase tracking-wider">
                    {alert.alert_type}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-600">{timeAgo(alert.created_at)}</span>
                  <button
                    onClick={() => resolveAlert(alert.id)}
                    className="text-xs text-gray-600 hover:text-gray-400 transition-colors"
                    title="Resolve"
                  >
                    ✕
                  </button>
                </div>
              </div>

              <p className="text-xs text-gray-400 mt-1.5 leading-relaxed line-clamp-2">
                {alert.description}
              </p>

              <div className="flex items-center gap-3 mt-2 text-xs text-gray-600">
                <span>{alert.value_eth.toFixed(2)} ETH</span>
                <span>·</span>
                <span>Risk: <strong className="text-gray-400">{alert.risk_score.toFixed(0)}</strong></span>
                {alert.wallet_address && (
                  <>
                    <span>·</span>
                    <a
                      href={`https://etherscan.io/address/${alert.wallet_address}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono hover:text-gray-300 transition-colors"
                    >
                      {alert.wallet_address.slice(0, 6)}…{alert.wallet_address.slice(-4)}
                    </a>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Alert } from '../services/api'

interface Props {
  alert: Alert | null
  onClose: () => void
}

export function NotificationToast({ alert, onClose }: Props) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (alert) {
      setVisible(true)
      const timer = setTimeout(() => {
        setVisible(false)
        setTimeout(onClose, 300) // allow animation to finish
      }, 5000)
      return () => clearTimeout(timer)
    }
  }, [alert, onClose])

  if (!alert) return null

  return (
    <div 
      className={`fixed top-20 right-8 z-[110] w-80 bg-gray-900 border border-red-900/50 rounded-xl shadow-2xl p-4 transition-all duration-300 transform ${
        visible ? 'translate-x-0 opacity-100' : 'translate-x-12 opacity-0'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-lg bg-red-950/50 flex items-center justify-center text-xl shrink-0">
          🚨
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-bold text-red-500 uppercase tracking-widest">Critical Alert</span>
            <button onClick={() => setVisible(false)} className="text-gray-500 hover:text-white">✕</button>
          </div>
          <h4 className="text-sm font-bold text-white truncate capitalize">
            {alert.alert_type.replace('_', ' ')}
          </h4>
          <p className="text-xs text-gray-400 mt-1 line-clamp-2">
            {alert.description}
          </p>
          <div className="mt-3 flex items-center justify-between">
            <span className="text-[10px] font-mono text-gray-600">
              {alert.tx_hash.slice(0, 10)}...
            </span>
            <span className="px-2 py-0.5 bg-red-500/10 text-red-400 text-[10px] font-bold rounded uppercase">
              Score: {alert.risk_score}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

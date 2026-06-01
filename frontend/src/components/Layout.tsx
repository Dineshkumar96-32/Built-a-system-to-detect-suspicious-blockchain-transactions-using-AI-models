import { ReactNode, useState, useCallback, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { SearchBar } from './SearchBar'
import { api, Alert } from '../services/api'
import { useStore } from '../store'
import { TransactionModal } from './TransactionModal'
import { NotificationToast } from './NotificationToast'

interface Props {
  children: ReactNode
}

export function Layout({ children }: Props) {
  const { alerts, metrics, selectedTx, setSelectedTx, wsConnected } = useStore()
  const [isSearching, setIsSearching] = useState(false)
  const [toastAlert, setToastAlert] = useState<Alert | null>(null)
  const navigate = useNavigate()

  const activeAlerts = alerts.filter((a) => !a.resolved)

  // Watch store for new high-risk alerts to show toasts
  useEffect(() => {
    const lastAlert = alerts[0]
    if (lastAlert && !lastAlert.resolved && (lastAlert.severity === 'high' || lastAlert.severity === 'critical')) {
      if (toastAlert?.id !== lastAlert.id) {
        setToastAlert(lastAlert)
      }
    }
  }, [alerts, toastAlert?.id])

  const handleSearch = async (query: string) => {
    setIsSearching(true)
    try {
      const results = await api.searchTransactions(query)
      if (results.length > 0) {
        const directMatch = results.find(t => t.hash.toLowerCase() === query.toLowerCase())
        setSelectedTx(directMatch || results[0])
      } else {
        alert('No transactions found for this query in recent history.')
      }
    } catch (err) {
      console.error('Search failed', err)
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="flex min-h-screen bg-gray-950 text-gray-100 font-mono">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-800 bg-gray-950 flex flex-col sticky top-0 h-screen shrink-0">
        <div className="p-6 flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center text-sm font-bold shadow-lg shadow-orange-900/20">
            ⛓
          </div>
          <span className="text-lg font-bold tracking-tight">BlockShield</span>
        </div>

        <nav className="flex-1 px-4 py-4 space-y-2">
          <NavItem to="/" icon="📊" label="Dashboard" />
          <NavItem to="/alerts" icon="🚨" label="Alert Feed" />
          <NavItem to="/analytics" icon="🕸" label="Network Analytics" />
          <NavItem to="/settings" icon="⚙️" label="Settings" />
        </nav>

        <div className="p-4 border-t border-gray-800 space-y-4">
          <div className="bg-gray-900 rounded-lg p-3 border border-gray-800">
            <div className="text-[10px] text-gray-500 uppercase font-bold mb-2">System Throughput</div>
            <div className="text-lg font-bold text-white">
              {metrics?.tx_per_second?.toFixed(1) ?? '0.0'}
              <span className="text-[10px] text-gray-500 ml-1">TX/S</span>
            </div>
          </div>
          <div className="text-[10px] text-gray-600 text-center uppercase tracking-widest font-bold">
            v1.0.4 Premium
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Global Header */}
        <header className="h-16 border-b border-gray-800 bg-gray-950/50 backdrop-blur sticky top-0 z-[60] flex items-center px-8 gap-8">
          <div className="flex-1 max-w-md">
            <SearchBar onSearch={handleSearch} isSearching={isSearching} />
          </div>

          <div className="flex items-center gap-6 ml-auto">
            {activeAlerts.length > 0 && (
              <div 
                className="flex items-center gap-2 px-3 py-1 bg-red-950/30 border border-red-900/50 rounded-full cursor-pointer hover:bg-red-950/50 transition-colors"
                onClick={() => navigate('/alerts')}
              >
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                <span className="text-[10px] text-red-400 font-bold uppercase tracking-wider">
                  {activeAlerts.length} Active Alerts
                </span>
              </div>
            )}
            
            <div className="flex items-center gap-3">
               <div className="text-right hidden sm:block">
                  <div className="text-[10px] text-gray-500 uppercase font-bold flex items-center justify-end gap-1.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'} ${wsConnected ? 'animate-pulse' : ''}`} />
                    Live Pipeline
                  </div>
                  <div className={`text-xs ${wsConnected ? 'text-green-400' : 'text-red-400'} font-bold`}>
                    {wsConnected ? 'Connected' : 'Disconnected'}
                  </div>
               </div>
               <div className="w-8 h-8 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center text-xs">
                  P
               </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1">
          {children}
        </main>
      </div>

      <TransactionModal 
        transaction={selectedTx} 
        onClose={() => setSelectedTx(null)} 
      />

      <NotificationToast 
        alert={toastAlert} 
        onClose={() => setToastAlert(null)} 
      />
    </div>
  )
}

function NavItem({ to, icon, label }: { to: string; icon: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-bold transition-all ${
          isActive
            ? 'bg-orange-600 text-white shadow-lg shadow-orange-900/20'
            : 'text-gray-500 hover:text-gray-300 hover:bg-gray-900'
        }`
      }
    >
      <span className="text-lg">{icon}</span>
      {label}
    </NavLink>
  )
}

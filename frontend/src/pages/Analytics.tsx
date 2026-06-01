// src/pages/Analytics.tsx
import { useState, useEffect } from 'react'
import { api, WalletProfile } from '../services/api'
import { RiskBadge } from '../components/RiskBadge'

import { NetworkGraph } from '../components/NetworkGraph'

export default function Analytics() {
  const [topWallets, setTopWallets] = useState<WalletProfile[]>([])
  const [graphData, setGraphData] = useState<{ nodes: any[]; links: any[] }>({ nodes: [], links: [] })
  const [loading, setLoading] = useState(true)
  const [graphLoading, setGraphLoading] = useState(true)

  useEffect(() => {
    api.getTopRiskWallets().then(setTopWallets).finally(() => setLoading(false))
    api.getNetworkGraph(100).then(setGraphData).finally(() => setGraphLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-mono p-8">
      <div className="max-w-screen-xl mx-auto space-y-8">
        <header>
          <h1 className="text-3xl font-bold tracking-tight">Network Analytics</h1>
          <p className="text-gray-500 mt-1">Deep-dive into wallet clusters and high-risk entities.</p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Top Risky Wallets */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl">
            <div className="px-6 py-4 border-b border-gray-800 bg-gray-950/50 flex items-center justify-between">
              <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">High-Risk Entities</h2>
              <span className="text-[10px] bg-orange-950/30 text-orange-400 border border-orange-900/50 px-2 py-0.5 rounded-full font-bold">TOP 20</span>
            </div>
            <div className="divide-y divide-gray-800/50">
              {loading ? (
                <div className="p-12 text-center text-gray-600">Analyzing network graph...</div>
              ) : topWallets.map(wallet => (
                <div key={wallet.address} className="px-6 py-4 flex items-center justify-between hover:bg-gray-800/30 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded bg-gray-800 flex items-center justify-center font-bold text-gray-500">
                      W
                    </div>
                    <div>
                      <div className="text-sm font-mono text-gray-200">{wallet.address.slice(0, 12)}...{wallet.address.slice(-8)}</div>
                      <div className="text-[10px] text-gray-500 uppercase tracking-wider mt-0.5">
                        {wallet.tx_count} TXs · {wallet.volume_eth.toFixed(2)} ETH Volume
                      </div>
                    </div>
                  </div>
                  <RiskBadge score={wallet.risk_score} />
                </div>
              ))}
            </div>
          </div>

          {/* Network Visualization */}
          <div className="space-y-8">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-0 shadow-xl aspect-square relative overflow-hidden">
              {graphLoading ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center space-y-4 bg-gray-900/50 backdrop-blur-sm z-10">
                   <div className="w-12 h-12 border-4 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
                   <p className="text-xs font-bold text-gray-400 uppercase tracking-widest">Building Relationship Graph...</p>
                </div>
              ) : (
                <NetworkGraph data={graphData} />
              )}
            </div>

            <div className="bg-gradient-to-br from-orange-600/20 to-red-600/20 border border-orange-900/30 rounded-xl p-6">
               <h3 className="text-sm font-bold text-orange-400 uppercase tracking-widest mb-2">Security Notice</h3>
               <p className="text-sm text-gray-300 leading-relaxed">
                  Graph analysis shows an increase in "multi-hop" mixer activity on Mainnet. 
                  Entities in the top list are being tracked for coordinated wash-trading patterns.
               </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

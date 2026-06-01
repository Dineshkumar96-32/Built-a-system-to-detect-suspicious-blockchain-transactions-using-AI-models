// src/components/TransactionModal.tsx
import type { Transaction } from '../services/api'
import { RiskBadge } from './RiskBadge'

interface Props {
  transaction: Transaction | null
  onClose: () => void
}

export function TransactionModal({ transaction, onClose }: Props) {
  if (!transaction) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div 
        className="w-full max-w-2xl bg-gray-900 border border-gray-800 rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between bg-gray-900/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center text-xl">
              {transaction.is_flagged ? '🚩' : '📄'}
            </div>
            <div>
              <h2 className="text-lg font-bold text-white leading-tight">Transaction Details</h2>
              <p className="text-xs text-gray-500 font-mono">{transaction.hash}</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto">
          {/* Risk Summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-gray-800/40 rounded-xl p-4 border border-gray-800/50">
              <div className="text-xs text-gray-500 mb-1 uppercase tracking-wider font-semibold">AI Risk Score</div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold text-white">{transaction.risk_score.toFixed(1)}</span>
                <RiskBadge score={transaction.risk_score} />
              </div>
            </div>
            <div className="bg-gray-800/40 rounded-xl p-4 border border-gray-800/50">
              <div className="text-xs text-gray-500 mb-1 uppercase tracking-wider font-semibold">Detection Type</div>
              <div className="text-xl font-bold text-white capitalize">
                {transaction.fraud_type?.replace('_', ' ') || 'Normal Transaction'}
              </div>
            </div>
          </div>

          {/* AI Signals */}
          <div>
            <h3 className="text-xs text-gray-500 mb-3 uppercase tracking-wider font-semibold">Detection Signals</h3>
            <div className="flex flex-wrap gap-2">
              {transaction.signals.length > 0 ? (
                transaction.signals.map((signal, i) => (
                  <span key={i} className="px-3 py-1 bg-red-950/30 border border-red-900/50 text-red-400 rounded-full text-xs">
                    {signal}
                  </span>
                ))
              ) : (
                <span className="text-gray-500 text-sm italic">No suspicious signals detected.</span>
              )}
            </div>
          </div>

          {/* Core Info */}
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-x-8 gap-y-4 text-sm">
              <div>
                <div className="text-gray-500 mb-1">Value</div>
                <div className="text-white font-mono">{transaction.value_eth.toFixed(6)} ETH</div>
              </div>
              <div>
                <div className="text-gray-500 mb-1">Gas Price</div>
                <div className="text-white font-mono">{transaction.gas_price_gwei.toFixed(2)} Gwei</div>
              </div>
              <div>
                <div className="text-gray-500 mb-1">Block Number</div>
                <div className="text-white font-mono">{transaction.block_number}</div>
              </div>
              <div>
                <div className="text-gray-500 mb-1">Timestamp</div>
                <div className="text-white">{new Date(transaction.timestamp).toLocaleString()}</div>
              </div>
            </div>

            <div className="pt-4 border-t border-gray-800 space-y-3 text-xs">
              <div>
                <div className="text-gray-500 mb-1 font-semibold uppercase">From Address</div>
                <div className="flex items-center justify-between p-2 bg-black/30 rounded border border-gray-800 font-mono text-gray-300">
                  <span>{transaction.from_address}</span>
                  <a href={`https://etherscan.io/address/${transaction.from_address}`} target="_blank" className="text-blue-400 hover:underline">View</a>
                </div>
              </div>
              <div>
                <div className="text-gray-500 mb-1 font-semibold uppercase">To Address</div>
                <div className="flex items-center justify-between p-2 bg-black/30 rounded border border-gray-800 font-mono text-gray-300">
                  <span>{transaction.to_address || 'Contract Creation'}</span>
                  {transaction.to_address && (
                    <a href={`https://etherscan.io/address/${transaction.to_address}`} target="_blank" className="text-blue-400 hover:underline">View</a>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-950/50 border-t border-gray-800 flex justify-end gap-3">
          <a 
            href={`https://etherscan.io/tx/${transaction.hash}`}
            target="_blank"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            View on Etherscan
          </a>
          <button 
            onClick={onClose}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-sm font-semibold rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

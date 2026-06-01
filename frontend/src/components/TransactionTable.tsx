// src/components/TransactionTable.tsx
import type { Transaction } from '../services/api'
import { RiskBadge, RiskDot } from './RiskBadge'

interface Props {
  transactions: Transaction[]
  onRowClick: (tx: Transaction) => void
}

function shortAddr(addr: string | null) {
  if (!addr) return '—'
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`
}

function shortHash(hash: string) {
  return `${hash.slice(0, 8)}…${hash.slice(-4)}`
}

export function TransactionTable({ transactions, onRowClick }: Props) {
  if (transactions.length === 0) {
    return (
      <div className="py-16 text-center text-gray-600 text-sm">
        Waiting for transactions…
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-600 border-b border-gray-800">
            <th className="text-left px-4 py-2 font-normal text-[10px] uppercase tracking-wider">Hash</th>
            <th className="text-left px-4 py-2 font-normal text-[10px] uppercase tracking-wider hidden sm:table-cell">From</th>
            <th className="text-right px-4 py-2 font-normal text-[10px] uppercase tracking-wider">Value (ETH)</th>
            <th className="text-right px-4 py-2 font-normal text-[10px] uppercase tracking-wider">Risk</th>
            <th className="text-left px-4 py-2 font-normal text-[10px] uppercase tracking-wider hidden md:table-cell">Type</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => (
            <tr
              key={tx.hash}
              onClick={() => onRowClick(tx)}
              className={`border-b border-gray-800/50 hover:bg-orange-500/5 cursor-pointer transition-all ${
                tx.is_flagged ? 'bg-red-950/10' : ''
              }`}
            >
              <td className="px-4 py-2.5 font-mono text-gray-400">
                <div className="flex items-center gap-2">
                  <RiskDot score={tx.risk_score} />
                  <span className="hover:text-white transition-colors">
                    {shortHash(tx.hash)}
                  </span>
                </div>
              </td>
              <td className="px-4 py-2.5 font-mono text-gray-500 hidden sm:table-cell">
                <span className="hover:text-gray-300 transition-colors">
                  {shortAddr(tx.from_address)}
                </span>
              </td>
              <td className="px-4 py-2.5 text-right text-gray-300">
                {tx.value_eth.toFixed(4)}
              </td>
              <td className="px-4 py-2.5 text-right">
                <RiskBadge score={tx.risk_score} />
              </td>
              <td className="px-4 py-2.5 hidden md:table-cell">
                {tx.fraud_type ? (
                  <span className="text-orange-400 capitalize">
                    {tx.fraud_type.replace('_', ' ')}
                  </span>
                ) : (
                  <span className="text-gray-700">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

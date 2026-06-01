// src/components/RiskBadge.tsx
interface Props {
  score: number
  size?: 'sm' | 'md'
}

function getRiskLevel(score: number): { label: string; classes: string } {
  if (score >= 85) return { label: 'CRITICAL', classes: 'bg-red-900/70 text-red-300 border-red-700' }
  if (score >= 65) return { label: 'HIGH',     classes: 'bg-orange-900/70 text-orange-300 border-orange-700' }
  if (score >= 45) return { label: 'MEDIUM',   classes: 'bg-yellow-900/70 text-yellow-300 border-yellow-700' }
  return               { label: 'LOW',      classes: 'bg-gray-800 text-gray-400 border-gray-700' }
}

export function RiskBadge({ score, size = 'sm' }: Props) {
  const { label, classes } = getRiskLevel(score)
  return (
    <span className={`border rounded px-1.5 py-0.5 text-xs font-mono font-bold ${classes}`}>
      {score.toFixed(0)} · {label}
    </span>
  )
}

export function RiskDot({ score }: { score: number }) {
  if (score >= 85) return <span className="inline-block w-2 h-2 rounded-full bg-red-500 animate-pulse" />
  if (score >= 65) return <span className="inline-block w-2 h-2 rounded-full bg-orange-500" />
  if (score >= 45) return <span className="inline-block w-2 h-2 rounded-full bg-yellow-500" />
  return <span className="inline-block w-2 h-2 rounded-full bg-gray-600" />
}

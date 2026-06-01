// src/components/MetricCard.tsx
type Color = 'blue' | 'green' | 'red' | 'purple' | 'orange'

const colorMap: Record<Color, string> = {
  blue:   'border-blue-800 bg-blue-950/30',
  green:  'border-green-800 bg-green-950/30',
  red:    'border-red-800 bg-red-950/30',
  purple: 'border-purple-800 bg-purple-950/30',
  orange: 'border-orange-800 bg-orange-950/30',
}

const textMap: Record<Color, string> = {
  blue:   'text-blue-400',
  green:  'text-green-400',
  red:    'text-red-400',
  purple: 'text-purple-400',
  orange: 'text-orange-400',
}

interface Props {
  label: string
  value: string
  sub: string
  icon: string
  color: Color
}

export function MetricCard({ label, value, sub, icon, color }: Props) {
  return (
    <div className={`border rounded-xl p-4 ${colorMap[color]}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 uppercase tracking-widest">{label}</span>
        <span className="text-lg">{icon}</span>
      </div>
      <div className={`text-2xl font-bold ${textMap[color]}`}>{value}</div>
      <div className="text-xs text-gray-600 mt-1">{sub}</div>
    </div>
  )
}

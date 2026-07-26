import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts'
import { getSnapshots } from '../../api/collection'
import type { Snapshot } from '../../types'

export default function CollectionGraph() {
  const [data, setData] = useState<Snapshot[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSnapshots().then(setData).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="h-64 flex items-center justify-center text-gray-500 text-sm">Loading graph…</div>
  if (data.length === 0) return (
    <div className="h-64 flex items-center justify-center text-gray-600 text-sm">
      Upload your collection to start tracking history.
    </div>
  )

  const formatted = data.map(s => ({
    date: new Date(s.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    'Comics': s.comic_count,
    'Cost Basis ($)': Number(s.total_paid.toFixed(2)),
    'Market Value ($)': Number(s.total_value.toFixed(2)),
  }))

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">Collection Over Time</h2>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={formatted} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis yAxisId="count" orientation="left" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={36} />
          <YAxis yAxisId="value" orientation="right" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} width={60} tickFormatter={v => `$${v}`} />
          <Tooltip
            contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
            labelStyle={{ color: '#9ca3af', marginBottom: 4 }}
            itemStyle={{ color: '#e5e7eb' }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: '#9ca3af', paddingTop: 12 }} />
          <Line yAxisId="count" type="monotone" dataKey="Comics" stroke="#60a5fa" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
          <Line yAxisId="value" type="monotone" dataKey="Cost Basis ($)" stroke="#34d399" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
          <Line yAxisId="value" type="monotone" dataKey="Market Value ($)" stroke="#e63b2e" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

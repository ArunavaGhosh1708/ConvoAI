import clsx from 'clsx'
import type { ReactNode } from 'react'

interface Props {
  label:    string
  value:    string | number
  sub?:     string
  icon:     ReactNode
  accent?:  'blue' | 'green' | 'amber' | 'purple'
  loading?: boolean
}

const ACCENT = {
  blue:   'bg-blue-50   text-blue-600',
  green:  'bg-green-50  text-green-600',
  amber:  'bg-amber-50  text-amber-600',
  purple: 'bg-purple-50 text-purple-600',
}

export function MetricsCard({ label, value, sub, icon, accent = 'blue', loading }: Props) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl bg-white p-5 shadow-sm border border-gray-100">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
        <div className={clsx('flex h-9 w-9 items-center justify-center rounded-xl', ACCENT[accent])}>
          {icon}
        </div>
      </div>
      {loading ? (
        <div className="h-8 w-24 animate-pulse rounded bg-gray-100" />
      ) : (
        <>
          <p className="text-3xl font-bold text-gray-800">{value}</p>
          {sub && <p className="text-xs text-gray-400">{sub}</p>}
        </>
      )}
    </div>
  )
}

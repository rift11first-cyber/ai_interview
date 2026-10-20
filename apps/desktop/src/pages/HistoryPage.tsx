import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Interview } from '@/lib/types'

export function HistoryPage() {
  const [rows, setRows] = useState<Interview[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listInterviews()
      .then(setRows)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="w-full max-w-4xl space-y-10">
      <header className="space-y-2">
        <h1 className="text-4xl text-sky-100" style={{ fontFamily: 'var(--font-display)' }}>
          History
        </h1>
        <p className="text-sky-100/45">Your recent practice sessions and evaluations.</p>
      </header>

      {error && <p className="border-l-2 border-red-400 pl-3 text-sky-200">{error}</p>}

      <div className="grid gap-3">
        {rows.length === 0 && !error && (
          <p className="text-sm text-sky-100/45">No interviews yet.</p>
        )}
        {rows.map((s) => (
          <div
            key={s.id}
            className="flex w-full flex-wrap items-center justify-between gap-5 border-b border-white/10 py-5 transition hover:border-sky-300/40"
          >
            <div>
              <div className="font-medium capitalize text-sky-100">
                {formatRole(s.role_id)}
              </div>
              <div className="mt-1 text-xs text-sky-100/40">
                {s.status} · {s.duration_minutes} minute session · {s.created_at?.slice?.(0, 10) || ''}
              </div>
            </div>
            <div className="flex items-center gap-5 text-sm">
              <Link className="text-sky-300 underline-offset-4 hover:text-sky-100 hover:underline" to={`/interview/${s.id}`}>
                Open interview
              </Link>
              {s.status === 'completed' && <Link className="text-sky-300/70 underline-offset-4 hover:text-sky-100 hover:underline" to={`/evaluation/${s.id}`}>View evaluation</Link>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function formatRole(roleId: string) {
  return roleId.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

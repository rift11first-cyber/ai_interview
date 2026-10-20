import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Evaluation } from '@/lib/types'
import { Button } from '@/components/ui/button'

export function EvaluationPage() {
  const { id } = useParams()
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api
      .getEvaluation(id)
      .then(setEvaluation)
      .catch((e) => setError(e.message))
  }, [id])

  if (error) {
    return <p className="text-sky-200">{error}</p>
  }
  if (!evaluation) {
    return <p className="text-sky-100/45">Generating evaluation…</p>
  }

  const dims = Object.entries(evaluation.dimensions)

  return (
    <div className="mx-auto w-full max-w-4xl space-y-10">
      <header className="space-y-3">
        <p className="text-xs uppercase tracking-[0.2em] text-sky-300">
          {evaluation.hiring_signal.replace('_', ' ')}
        </p>
        <h1 className="text-5xl text-sky-100" style={{ fontFamily: 'var(--font-display)' }}>
          Evaluation
        </h1>
        <p className="text-lg text-sky-100/45">
          Overall score{' '}
          <span className="font-semibold text-sky-200">
            {evaluation.overall_score.toFixed(1)}
          </span>{' '}
          / 10
        </p>
      </header>

      <p className="max-w-3xl border-l-2 border-sky-300/50 pl-5 leading-relaxed text-sky-100/65">
        {evaluation.summary}
      </p>
      <div className="grid gap-0 border-y border-white/10 sm:grid-cols-3">
        {evaluation.rounds.map((round) => (
          <div key={round.index} className="border-b border-white/10 py-4 sm:border-b-0 sm:border-r sm:px-5 first:pl-0 last:border-r-0">
            <p className="text-sm font-medium text-sky-100">Round {round.index}: {round.name}</p>
            <p className="mt-2 text-sm font-semibold text-sky-200">
              {round.status === 'passed' ? `Passed · ${round.score}/10` : round.status === 'failed' ? `Not passed · ${round.score}/10` : 'Not completed'}
            </p>
            {round.feedback && <p className="mt-1 text-xs text-sky-100/40">{round.feedback}</p>}
          </div>
        ))}
      </div>

      <div className="grid gap-x-10 sm:grid-cols-2">
        {dims.map(([key, dim]) => (
          <div key={key} className="border-b border-white/10 py-5">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold capitalize text-sky-100">{key.replaceAll('_', ' ')}</h3>
              <span className="text-lg font-medium text-sky-200">
                {dim.score.toFixed(1)}
              </span>
            </div>
            <div className="mb-3 h-1 overflow-hidden rounded-full bg-black">
              <div
                className="h-full border border-sky-300 bg-black"
                style={{ width: `${Math.min(100, dim.score * 10)}%` }}
              />
            </div>
            <p className="text-sm text-sky-100/45">{dim.rationale}</p>
          </div>
        ))}
      </div>

      <section className="space-y-3">
        <h2 className="text-2xl text-sky-100" style={{ fontFamily: 'var(--font-display)' }}>
          Recommendations
        </h2>
        <ul className="divide-y divide-white/10 border-y border-white/10">
          {evaluation.recommendations.map((r) => (
            <li
              key={r}
              className="py-4 text-sm text-sky-100/60"
            >
              {r}
            </li>
          ))}
        </ul>
      </section>

      <div className="flex gap-3">
        <Link to="/setup">
          <Button>New interview</Button>
        </Link>
        <Link to="/history">
        <Button variant="ghost">History</Button>
        </Link>
      </div>
      <p className="text-xs text-sky-100/25">{evaluation.model}</p>
    </div>
  )
}

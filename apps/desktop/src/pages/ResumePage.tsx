import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Resume } from '@/lib/types'
import { Button } from '@/components/ui/button'

export function ResumePage() {
  const [resumes, setResumes] = useState<Resume[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Resume | null>(null)

  async function refresh() {
    const rows = await api.listResumes()
    setResumes(rows)
    if (rows[0]) setSelected(rows[0])
  }

  useEffect(() => {
    refresh().catch((e) => setError(e.message))
  }, [])

  async function onFile(file: File | null) {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const resume = await api.uploadResume(file)
      await refresh()
      setSelected(resume)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-4xl text-sky-100" style={{ fontFamily: 'var(--font-display)' }}>
            Resume
          </h1>
          <p className="text-sky-100/45">Upload a PDF and we’ll turn it into interview context.</p>
        </div>
        <label className="inline-flex h-10 cursor-pointer items-center justify-center rounded-full border border-sky-300 bg-black px-5 text-sm font-medium text-sky-200 hover:bg-black/80">
          <input
            type="file"
            accept="application/pdf"
            className="hidden"
            disabled={uploading}
            onChange={(e) => onFile(e.target.files?.[0] ?? null)}
          />
          {uploading ? 'Parsing…' : 'Upload PDF'}
        </label>
      </header>

      {error && (
        <p className="border-l-2 border-red-400 pl-4 text-sm text-sky-200">
          {error}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-2">
          {resumes.length === 0 && (
            <p className="text-sm text-sky-100/45">No resumes yet.</p>
          )}
          {resumes.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => setSelected(r)}
              className={`w-full border-b border-white/10 px-2 py-4 text-left text-sm transition ${
                selected?.id === r.id
                  ? 'border-sky-300 text-sky-100'
                  : 'text-sky-100/55 hover:text-sky-100'
              }`}
            >
              <div className="font-medium truncate">{r.original_filename}</div>
              <div className="mt-1 text-xs text-sky-100/35">{r.parse_status}</div>
            </button>
          ))}
        </aside>

        <section className="min-w-0 lg:pl-10">
          {!selected && <p className="text-sky-100/45">Select a resume to inspect.</p>}
          {selected?.parsed && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl" style={{ fontFamily: 'var(--font-display)' }}>
                  {selected.parsed.full_name || 'Candidate'}
                </h2>
                <p className="text-sm text-sky-100/40">
                  {[selected.parsed.email, selected.parsed.phone].filter(Boolean).join(' · ')}
                </p>
              </div>
              {selected.parsed.summary && (
                <p className="max-w-2xl text-sm leading-relaxed text-sky-100/65">{selected.parsed.summary}</p>
              )}
              <div>
                  <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-sky-300/70">
                  Skills
                </h3>
                <div className="flex flex-wrap gap-2">
                  {selected.parsed.skills.map((s) => (
                    <span
                      key={s}
                      className="border-b border-sky-300/30 px-1 py-1 text-xs text-sky-100/70"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-sky-300/70">
                  Projects
                </h3>
                <ul className="space-y-3">
                  {selected.parsed.projects.map((p) => (
                    <li key={p.name} className="border-t border-white/10 py-4">
                      <div className="font-medium text-sky-100">{p.name}</div>
                      <p className="mt-1 text-sm text-sky-100/50">{p.description}</p>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-sky-300/70">
                  Experience
                </h3>
                {selected.parsed.experience.length === 0 ? (
                  <p className="text-sm text-sky-100/45">No experience detected.</p>
                ) : (
                  <ul className="space-y-3">
                    {selected.parsed.experience.map((e) => (
                      <li key={`${e.company}-${e.title}`} className="border-t border-white/10 py-4">
                        <div className="font-medium text-sky-100">{e.title}</div>
                        <div className="text-sm text-sky-100/45">
                          {e.company}
                          {e.dates ? ` · ${e.dates}` : ''}
                        </div>
                        {e.bullets.length > 0 && (
                          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-sky-100/55">
                            {e.bullets.map((b, i) => (
                              <li key={i}>{b}</li>
                            ))}
                          </ul>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-sky-300/70">
                  Education
                </h3>
                {selected.parsed.education.length === 0 ? (
                  <p className="text-sm text-sky-100/45">No education detected.</p>
                ) : (
                  <ul className="space-y-2">
                    {selected.parsed.education.map((e, i) => (
                    <li key={i} className="border-t border-white/10 py-4">
                        <div className="font-medium text-sky-100">{e.degree}</div>
                        <div className="text-sm text-sky-100/45">
                          {e.institution}
                          {e.field ? ` · ${e.field}` : ''}
                          {e.dates ? ` · ${e.dates}` : ''}
                          {e.gpa ? ` · GPA ${e.gpa}` : ''}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <Link to="/setup">
                <Button>Continue to interview setup</Button>
              </Link>
            </div>
          )}
          {selected && !selected.parsed && (
            <p className="text-sky-100/45">Parse status: {selected.parse_status}</p>
          )}
        </section>
      </div>
    </div>
  )
}

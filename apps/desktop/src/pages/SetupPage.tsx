import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Resume, Role } from '@/lib/types'
import { Button } from '@/components/ui/button'

export function SetupPage() {
  const navigate = useNavigate()
  const [resumes, setResumes] = useState<Resume[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [resumeId, setResumeId] = useState('')
  const [roleId, setRoleId] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.listResumes(), api.listRoles()])
      .then(([r, roleRows]) => {
        const parsedResumes = r.filter((x) => x.parse_status === 'ok')
        setResumes(parsedResumes)
        setRoles(roleRows)
        if (parsedResumes[0]) setResumeId(parsedResumes[0].id)
        if (roleRows[0]) setRoleId(roleRows[0].id)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoadingOptions(false))
  }, [])

  async function start() {
    if (!resumeId || !roleId) {
      setError('Select a resume and role')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const session = await api.createInterview({
        resume_id: resumeId,
        role_id: roleId,
      })
      const started = await api.startInterview(session.id)
      navigate(`/interview/${started.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-12">
      <header className="space-y-2">
        <h1 className="text-4xl text-sky-100" style={{ fontFamily: 'var(--font-display)' }}>
          Interview setup
        </h1>
        <p className="max-w-xl text-sky-100/45">
          Choose a resume and role. Sara will adapt the conversation to your level.
        </p>
      </header>

      <div className="max-w-xl space-y-8">
        <Field label="Resume">
          <select
            className="h-12 w-full border-b border-white/15 bg-transparent px-0 text-sm text-sky-100 outline-none focus:border-sky-300 [color-scheme:dark]"
            value={resumeId}
            onChange={(e) => setResumeId(e.target.value)}
          >
            {resumes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.original_filename}
                {r.parsed?.full_name ? ` — ${r.parsed.full_name}` : ''}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Role">
          <select
            className="h-12 w-full border-b border-white/15 bg-transparent px-0 text-sm text-sky-100 outline-none focus:border-sky-300 [color-scheme:dark]"
            value={roleId}
            onChange={(e) => setRoleId(e.target.value)}
          >
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title} · {r.level.replace('_', ' ')}
              </option>
            ))}
          </select>
        </Field>

        {error && <p className="border-l-2 border-red-400 pl-4 text-sm text-sky-200">{error}</p>}

        <Button onClick={start} disabled={loading || loadingOptions || !resumeId || !roleId}>
          {loadingOptions ? 'Loading options…' : loading ? 'Starting…' : 'Begin 45-minute interview'}
        </Button>
        {!loadingOptions && !resumes.length && (
          <p className="text-sm text-sky-100/45">Upload a parsed resume first.</p>
        )}
        {!loadingOptions && !roles.length && (
          <p className="text-sm text-sky-200">No roles are available. Restart the backend and reload.</p>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-2">
      <span className="text-xs font-medium uppercase tracking-[0.18em] text-sky-300/70">{label}</span>
      {children}
    </label>
  )
}

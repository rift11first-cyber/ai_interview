import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import type { ModelOption } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const DISMISS_KEY = 'interviewiq-onboarded'

/**
 * First-run gate: asks for the OpenRouter key + a free model up front,
 * so resume parsing and Sara interviews run on the LLM from the start.
 * Dismissable — the app keeps working offline with heuristic fallbacks.
 */
export function OnboardingGate() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [apiKey, setApiKey] = useState('')
  const [models, setModels] = useState<ModelOption[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [chatModel, setChatModel] = useState('')
  const [checking, setChecking] = useState(false)
  const [keyMsg, setKeyMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (localStorage.getItem(DISMISS_KEY)) return
    api
      .getSettings()
      .then((s) => {
        if (!s.has_api_key) {
          setChatModel(s.chat_model)
          setOpen(true)
        } else {
          localStorage.setItem(DISMISS_KEY, '1')
        }
      })
      .catch(() => {
        /* backend down — don't block the app */
      })
  }, [])

  useEffect(() => {
    if (!open) return
    api
      .listModels(true)
      .then((rows) => {
        setModels(rows)
        setModelsLoading(false)
      })
      .catch(() => setModelsLoading(false))
  }, [open ])

  async function verify() {
    if (!apiKey.trim()) {
      setKeyMsg({ ok: false, text: 'Paste your key first.' })
      return
    }
    setChecking(true)
    setKeyMsg(null)
    try {
      const r = await api.verifyKey(apiKey.trim())
      setKeyMsg(
        r.valid
          ? { ok: true, text: 'Key works — you can save and start.' }
          : { ok: false, text: r.error || 'Key looks invalid.' },
      )
    } catch (e) {
      setKeyMsg({ ok: false, text: e instanceof Error ? e.message : 'Verification failed' })
    } finally {
      setChecking(false)
    }
  }

  async function save() {
    if (!apiKey.trim()) {
      setError('Paste your OpenRouter key, or continue offline.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await api.updateSettings({
        openrouter_api_key: apiKey.trim(),
        chat_model: chatModel || undefined,
      })
      localStorage.setItem(DISMISS_KEY, '1')
      setOpen(false)
      navigate('/resume')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  function skip() {
    localStorage.setItem(DISMISS_KEY, '1')
    setOpen(false)
  }

  if (!open) return null

  const modelKnown = models.some((m) => m.id === chatModel)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6">
      <div className="w-full max-w-md space-y-6 border-l-2 border-sky-300 pl-6">
        <div className="space-y-1">
          <h2
            className="text-2xl text-sky-100"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Connect OpenRouter
          </h2>
          <p className="text-sm text-sky-100/50">
            Add a key for personalized parsing and interviews. Free models cost $0.{' '}
            <a className="text-sky-300 underline underline-offset-4" href="https://openrouter.ai/keys" target="_blank" rel="noreferrer">
              openrouter.ai/keys
            </a>
            .
          </p>
        </div>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-sky-300/70">API key</span>
          <div className="flex gap-2">
            <Input
              type="password"
              placeholder="sk-or-…"
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value)
                setKeyMsg(null)
              }}
              onKeyDown={(e) => e.key === 'Enter' && verify()}
            />
            <Button variant="secondary" onClick={verify} disabled={checking}>
              {checking ? '…' : 'Verify'}
            </Button>
          </div>
          {keyMsg && (
            <p className="text-sm text-sky-200">{keyMsg.text}</p>
          )}
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-sky-300/70">Model</span>
          {modelsLoading ? (
            <p className="text-sm text-sky-100/45">Loading free models…</p>
          ) : models.length > 0 ? (
            <select
              className="h-11 w-full rounded-xl border border-white/15 bg-black px-3 text-sm text-sky-100 outline-none focus:border-sky-300 [color-scheme:dark]"
              value={modelKnown ? chatModel : ''}
              onChange={(e) => setChatModel(e.target.value)}
            >
              {!modelKnown && <option value="">{chatModel} (current)</option>}
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          ) : (
            <Input
              value={chatModel}
              onChange={(e) => setChatModel(e.target.value)}
              placeholder="model id, e.g. …/llama-3.3-70b-instruct:free"
            />
          )}
        </label>

        {error && <p className="border-l-2 border-red-400 pl-3 text-sm text-sky-200">{error}</p>}

        <div className="flex items-center gap-3">
          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save & start'}
          </Button>
          <button onClick={skip} className="text-sm text-sky-100/45 underline underline-offset-4">
            Continue offline instead
          </button>
        </div>
      </div>
    </div>
  )
}

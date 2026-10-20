import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { ModelOption, Settings } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [models, setModels] = useState<ModelOption[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [chatModel, setChatModel] = useState('')
  const [customModel, setCustomModel] = useState(false)
  const [keyState, setKeyState] = useState<'idle' | 'checking' | 'valid' | 'invalid'>('idle')
  const [keyMsg, setKeyMsg] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setSettings(s)
        setChatModel(s.chat_model)
      })
      .catch((e) => setStatus(e.message))
    api
      .listModels(true)
      .then((rows) => {
        setModels(rows)
        setModelsLoading(false)
      })
      .catch(() => {
        setModels([])
        setModelsLoading(false)
      })
  }, [])

  const modelKnown = models.some((m) => m.id === chatModel)

  async function verify() {
    setKeyState('checking')
    setKeyMsg(null)
    try {
      const r = await api.verifyKey(apiKey || undefined)
      if (r.valid) {
        setKeyState('valid')
        setKeyMsg(r.label ? `Key works${r.label ? ` (${r.label})` : ''}.` : 'Key works.')
      } else {
        setKeyState('invalid')
        setKeyMsg(r.error || 'Key looks invalid.')
      }
    } catch (e) {
      setKeyState('invalid')
      setKeyMsg(e instanceof Error ? e.message : 'Verification failed')
    }
  }

  async function save() {
    setSaving(true)
    setStatus(null)
    try {
      const next = await api.updateSettings({
        openrouter_api_key: apiKey || undefined,
        chat_model: chatModel || undefined,
      })
      setSettings(next)
      setApiKey('')
      setKeyState('idle')
      setKeyMsg(null)
      setStatus('Saved. Sara will use the selected model from now on.')
    } catch (e) {
      setStatus(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl space-y-12">
      <header className="space-y-2">
        <h1 className="text-4xl text-sky-100" style={{ fontFamily: 'var(--font-display)' }}>
          Settings
        </h1>
        <p className="max-w-xl text-sky-100/45">
          Connect a model for personalized interviews. Your key stays on this machine.{' '}
          <a
            className="text-sky-300 underline underline-offset-4"
            href="https://openrouter.ai/keys"
            target="_blank"
            rel="noreferrer"
          >
            openrouter.ai/keys
          </a>
          .
        </p>
      </header>

      <div className="max-w-xl space-y-9">
        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-sky-300/70">OpenRouter API key</span>
          <div className="flex gap-2">
            <Input
              type="password"
              placeholder={settings?.has_api_key ? '•••••••• (saved)' : 'sk-or-…'}
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value)
                setKeyState('idle')
                setKeyMsg(null)
              }}
            />
            <Button variant="secondary" onClick={verify} disabled={keyState === 'checking'}>
              {keyState === 'checking' ? 'Checking…' : 'Verify'}
            </Button>
          </div>
          {keyState === 'valid' && <p className="text-sm text-sky-200">✓ {keyMsg}</p>}
          {keyState === 'invalid' && <p className="text-sm text-sky-200">{keyMsg}</p>}
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-sky-300/70">Chat model</span>
          {modelsLoading ? (
            <p className="text-sm text-sky-100/45">Loading free models…</p>
          ) : models.length > 0 && !customModel ? (
            <>
              <select
                className="h-11 w-full rounded-xl border border-white/15 bg-black px-3 text-sm text-sky-100 outline-none focus:border-sky-300 [color-scheme:dark]"
                value={modelKnown ? chatModel : ''}
                onChange={(e) => {
                  if (e.target.value === '__custom__') setCustomModel(true)
                  else setChatModel(e.target.value)
                }}
              >
                {!modelKnown && <option value="">{chatModel} (current — not in free list)</option>}
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
                <option value="__custom__">Custom model id…</option>
              </select>
              <p className="text-xs text-sky-100/35">
                {models.length} free models available.
              </p>
            </>
          ) : (
            <>
              <Input
                value={chatModel}
                onChange={(e) => setChatModel(e.target.value)}
                placeholder="e.g. meta-llama/llama-3.3-70b-instruct:free"
              />
              {models.length > 0 && (
                <button
                  className="text-xs font-medium text-sky-300 underline underline-offset-4"
                  onClick={() => setCustomModel(false)}
                >
                  ← back to free-model list
                </button>
              )}
              {models.length === 0 && (
                  <p className="text-xs text-sky-100/35">
                  Catalogue unavailable — enter a model id manually.
                </p>
              )}
            </>
          )}
        </label>

        <div className="flex items-center gap-3">
          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
          {status && <p className="text-sm text-sky-100/55">{status}</p>}
        </div>
        {settings && (
          <p className="border-t border-white/10 pt-4 text-xs text-sky-100/30">
            API key configured: {settings.has_api_key ? 'yes' : 'no'} · Active model:{' '}
            {settings.chat_model} · Embeddings: {settings.embedding_model}
          </p>
        )}
      </div>
    </div>
  )
}

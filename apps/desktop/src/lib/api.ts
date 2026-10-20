export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8765'

export function backendOfflineMessage() {
  return (
    `Cannot reach the backend at ${API_BASE}. ` +
    'Start it first with: cd backend && uv run interviewiq — then reload this page.'
  )
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new Error(backendOfflineMessage())
  }
  if (!res.ok) {
    let message = res.statusText
    try {
      const body = await res.json()
      message = body.error || body.detail || message
    } catch {
      /* ignore */
    }
    throw new Error(message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; version: string }>('/health'),
  getSettings: () => request<import('./types').Settings>('/settings'),
  updateSettings: (body: {
    openrouter_api_key?: string
    chat_model?: string
    embedding_model?: string
  }) =>
    request<import('./types').Settings>('/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  listResumes: () => request<import('./types').Resume[]>('/resumes'),
  uploadResume: async (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request<import('./types').Resume>('/resumes', { method: 'POST', body: fd })
  },
  listRoles: () => request<import('./types').Role[]>('/roles'),
  listInterviews: () => request<import('./types').Interview[]>('/interviews'),
  createInterview: (body: {
    resume_id: string
    role_id: string
    mode?: string
  }) =>
    request<import('./types').Interview>('/interviews', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'voice+text', ...body }),
    }),
  getInterview: (id: string) => request<import('./types').Interview>(`/interviews/${id}`),
  startInterview: (id: string) =>
    request<import('./types').Interview>(`/interviews/${id}/start`, { method: 'POST' }),
  answerInterview: (id: string, answer_text: string) =>
    request<import('./types').Interview>(`/interviews/${id}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer_text }),
    }),
  completeInterview: (id: string) =>
    request<import('./types').Interview>(`/interviews/${id}/complete`, { method: 'POST' }),
  completeRound: (id: string) =>
    request<import('./types').Interview>(`/interviews/${id}/round-complete`, { method: 'POST' }),
  getEvaluation: (id: string) =>
    request<import('./types').Evaluation>(`/interviews/${id}/evaluation`),
  listModels: (freeOnly = true) =>
    request<import('./types').ModelOption[]>(`/settings/models?free_only=${freeOnly}`),
  verifyKey: (openrouter_api_key?: string) =>
    request<import('./types').KeyVerification>('/settings/verify-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ openrouter_api_key: openrouter_api_key ?? null }),
    }),
  voiceConfig: () =>
    request<{
      interviewer_name: string
      input_modes: string[]
      output_modes: string[]
      stt: Record<string, unknown>
      tts: Record<string, unknown>
    }>('/voice/config'),
  voiceSpeak: (text: string) =>
    request<{ original: string; speakable: string }>('/voice/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),
}

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { Interview } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useLeoSpeech } from '@/lib/speech'

export function InterviewPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [interview, setInterview] = useState<Interview | null>(null)
  const [answer, setAnswer] = useState('')
  const [interim, setInterim] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [secondsLeft, setSecondsLeft] = useState(0)
  const roundEnding = useRef(false)
  const spokenForTurn = useRef<number | null>(null)
  const {
    listening,
    speaking,
    supported,
    speak,
    stopSpeaking,
    listen,
    stopListening,
  } = useLeoSpeech()

  useEffect(() => {
    if (!id) return
    api
      .getInterview(id)
      .then(setInterview)
      .catch((e) => setError(e.message))
  }, [id])

  useEffect(() => {
    if (!interview?.started_at || interview.status !== 'in_progress') return
    const tick = () => {
      const total = interview.duration_minutes * 60
      const elapsed = interview.elapsed_seconds + (Date.now() - Date.parse(interview.started_at!)) / 1000
      const priorRounds = interview.rounds.slice(0, interview.current_round - 1).reduce((sum, round) => sum + round.duration_minutes * 60, 0)
      const roundRemaining = Math.max(0, interview.rounds[interview.current_round - 1].duration_minutes * 60 - (elapsed - priorRounds))
      setSecondsLeft(Math.max(0, total - elapsed))
      if (roundRemaining <= 0 && !roundEnding.current) {
        roundEnding.current = true
        api.completeRound(interview.id).then(setInterview).catch((e) => setError(e.message)).finally(() => { roundEnding.current = false })
      }
    }
    tick()
    const timer = window.setInterval(tick, 1000)
    return () => window.clearInterval(timer)
  }, [interview])

  const openQuestion = useMemo(() => {
    if (!interview) return null
    const turns = interview.turns
    const last = turns[turns.length - 1]
    if (!last || last.answer_text) return null
    return last
  }, [interview])

  // Sara asks each new question out loud (voice) AND shows the text.
  useEffect(() => {
    if (!openQuestion) return
    if (spokenForTurn.current === openQuestion.turn_index) return
    spokenForTurn.current = openQuestion.turn_index
    // Start speaking immediately while the question is already visible as text.
    speak(openQuestion.question_text)
    return () => {
      stopSpeaking()
    }
  }, [openQuestion, speak, stopSpeaking])

  async function submit(text?: string) {
    const value = (text ?? answer).trim()
    if (!id || !value || busy) return
    stopSpeaking()
    stopListening()
    setBusy(true)
    setError(null)
    try {
      // LLM + RAG generate the next question from the resume + THIS answer
      // inside POST /interviews/{id}/answer (Sara agent, backend).
      const next = await api.answerInterview(id, value)
      setInterview(next)
      setAnswer('')
      setInterim('')
      if (next.status === 'completed') {
        navigate(`/evaluation/${next.id}`)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Submit failed')
    } finally {
      setBusy(false)
    }
  }

  function toggleMic() {
    if (listening) {
      stopListening()
      return
    }
    stopSpeaking()
    const ok = listen(
      (final) => {
        // Append dictated speech to the answer box; user can edit before sending.
        setAnswer((prev) => (prev ? `${prev} ${final}` : final))
        setInterim('')
      },
      (partial) => setInterim(partial),
    )
    if (!ok) setError('Voice input not supported in this browser — please type instead.')
  }

  async function finishEarly() {
    if (!id) return
    stopSpeaking()
    stopListening()
    setBusy(true)
    try {
      const next = await api.completeInterview(id)
      navigate(`/evaluation/${next.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not complete')
    } finally {
      setBusy(false)
    }
  }

  async function repeatQuestion() {
    if (!openQuestion) return
    try {
      const r = await api.voiceSpeak(openQuestion.question_text)
      speak(r.speakable)
    } catch {
      speak(openQuestion.question_text)
    }
  }

  if (!interview) {
    return <p className="text-sky-100/45">{error || 'Loading interview with Sara…'}</p>
  }

  const progress = Math.min(100, ((interview.duration_minutes * 60 - secondsLeft) / (interview.duration_minutes * 60)) * 100)
  const currentRound = interview.rounds[interview.current_round - 1]
  const formatTime = (seconds: number) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`

  return (
    <div className="mx-auto max-w-6xl space-y-10">
      <header className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className="flex h-11 w-11 items-center justify-center rounded-full border border-sky-300 bg-black text-lg font-bold text-sky-200"
              title="Sara — AI interviewer"
            >
              S
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-sky-300">
                Sara · {currentRound?.name} · Round {interview.current_round}/{interview.rounds.length}
              </p>
              <p className="text-sm text-sky-100/45">{formatTime(secondsLeft)} remaining</p>
            </div>
          </div>
          <Button variant="ghost" className="text-sky-100/55" onClick={finishEarly} disabled={busy}>
            End & evaluate
          </Button>
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-black">
          <div
            className="h-full rounded-full border border-sky-300 bg-black transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        {!supported.stt && (
          <p className="text-xs text-sky-100/45">
            Microphone input is unavailable in this browser. You can still type your answer.
          </p>
        )}
      </header>

      {openQuestion && (
        <section className="grid gap-12 border-t border-white/10 pt-8 lg:grid-cols-2 lg:gap-16">
          <div className="space-y-7 lg:border-r lg:border-white/10 lg:pr-16">
            <div className="flex items-center gap-3 text-xs uppercase tracking-[0.18em] text-sky-300/65">
              <span>Sara · {openQuestion.question_type}</span>
              <span className="text-sky-100/30">{formatTime(secondsLeft)} left</span>
            </div>
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-sky-300 bg-black text-sm font-bold text-sky-200">S</div>
              <p className="text-2xl leading-relaxed tracking-[-0.02em] text-sky-50">
                {openQuestion.question_text}
              </p>
            </div>
            <div className="flex items-center gap-3 text-sm text-sky-100/45">
              <span className={`h-2 w-2 rounded-full ${speaking ? 'animate-pulse bg-sky-300' : 'bg-white/20'}`} />
              <span>{speaking ? 'Sara is speaking…' : 'Question ready'}</span>
              <button onClick={repeatQuestion} className="ml-2 text-sky-300 underline-offset-4 hover:underline">
                Replay
              </button>
            </div>
          </div>

          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.18em] text-sky-300/65">Your answer</p>
                <p className="mt-2 text-sm text-sky-100/45">Speak first. Your words will appear here as text.</p>
              </div>
              {supported.stt && (
                <button
                  onClick={toggleMic}
                  disabled={busy}
                  className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-sky-300 bg-black text-xl text-sky-200 transition hover:bg-black/80 ${listening ? 'animate-pulse' : ''}`}
                  title={listening ? 'Stop listening' : 'Answer with voice'}
                >
                  {listening ? '⏹' : '🎙'}
                </button>
              )}
            </div>
            {listening && <p className="border-l-2 border-sky-300 pl-3 text-sm text-sky-200">{interim || 'Listening… speak your answer.'}</p>}
            <Textarea
              className="min-h-48 resize-none border-0 border-b border-white/15 bg-transparent px-0 text-lg text-sky-50 placeholder:text-sky-100/25 focus:border-sky-300 focus:ring-0"
              placeholder={supported.stt ? 'Your spoken answer will appear here…' : 'Type your answer…'}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              disabled={busy}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit()
              }}
            />
            {error && <p className="border-l-2 border-red-400 pl-3 text-sm text-sky-200">{error}</p>}
            <div className="flex items-center gap-4">
              <Button className="rounded-full px-6" onClick={() => submit()} disabled={busy || !answer.trim()}>
                {busy ? 'Sara is thinking…' : 'Send answer'}
              </Button>
              <span className="text-xs text-sky-100/30">⌘ / Ctrl + Enter</span>
            </div>
          </div>
        </section>
      )}

      {!openQuestion && interview.status === 'completed' && (
        <div className="border-t border-white/10 py-8">
          <p className="mb-4 text-sky-100">Interview complete — Sara has everything she needs.</p>
          <Link to={`/evaluation/${interview.id}`}>
            <Button>View evaluation</Button>
          </Link>
        </div>
      )}

      <details className="border-t border-white/10 pt-5 text-sm" open>
        <summary className="cursor-pointer font-medium text-sky-100/55">
          Transcript so far (voice + text)
        </summary>
        <div className="mt-4 space-y-4">
          {interview.turns.map((t) => (
            <div key={t.id} className="space-y-1">
              <p className="text-sky-100/65">
                <span className="font-medium text-sky-300">
                  Sara Q{t.turn_index}:
                </span>{' '}
                {t.question_text}
              </p>
              {t.answer_text ? (
                <p className="text-sky-100/45">
                  <span className="font-medium">You:</span> {t.answer_text}
                </p>
              ) : (
                <p className="text-xs italic text-sky-100/30">Awaiting your answer…</p>
              )}
            </div>
          ))}
        </div>
      </details>

      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}

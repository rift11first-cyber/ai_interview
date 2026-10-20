import { useCallback, useEffect, useRef, useState } from 'react'

type RecogCtor = new () => SpeechRecognitionLike

interface SpeechRecognitionLike {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: SpeechRecognitionEventLike) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort?: () => void
}

interface SpeechRecognitionEventLike {
  results: ArrayLike<{
    isFinal: boolean
    0: { transcript: string }
  }>
  resultIndex: number
}

function getRecognitionCtor(): RecogCtor | null {
  const w = window as unknown as Record<string, unknown>
  const ctor = (w.SpeechRecognition ?? w.webkitSpeechRecognition) as RecogCtor | undefined
  return ctor ?? null
}

export function useLeoSpeech() {
  const [voiceOn, setVoiceOn] = useState(true) // Sara speaks questions
  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [supported] = useState(() => ({
    tts: 'speechSynthesis' in window,
    stt: getRecognitionCtor() !== null,
  }))
  const recogRef = useRef<SpeechRecognitionLike | null>(null)
  const speakToken = useRef(0)

  const stopSpeaking = useCallback(() => {
    speakToken.current += 1
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [])

  const speak = useCallback(
    (text: string, rate = 1.0) => {
      if (!voiceOn || !('speechSynthesis' in window)) return
      const token = ++speakToken.current
      window.speechSynthesis.cancel()
      const clean = text.replace(/\s+/g, ' ').trim()
      if (!clean) return
      const utter = new SpeechSynthesisUtterance(clean)
      utter.lang = 'en-US'
      utter.rate = rate
      utter.pitch = 1.0
      // Prefer a natural English voice when available.
      const pickVoice = () => {
        const voices = window.speechSynthesis.getVoices()
        const en = voices.find((v) => v.lang.startsWith('en') && /natural|neural|google|aria|jenny|samantha/i.test(v.name))
          ?? voices.find((v) => v.lang.startsWith('en-US'))
          ?? voices.find((v) => v.lang.startsWith('en'))
        if (en) utter.voice = en
      }
      pickVoice()
      utter.onstart = () => token === speakToken.current && setSpeaking(true)
      utter.onend = () => token === speakToken.current && setSpeaking(false)
      utter.onerror = () => token === speakToken.current && setSpeaking(false)
      window.speechSynthesis.speak(utter)
    },
    [voiceOn],
  )

  const listen = useCallback(
    (onFinal: (transcript: string) => void, onInterim?: (transcript: string) => void) => {
      const Ctor = getRecognitionCtor()
      if (!Ctor) return false
      try {
        recogRef.current?.abort?.()
      } catch {
        /* ignore */
      }
      const recog = new Ctor()
      recogRef.current = recog
      recog.lang = 'en-US'
      recog.interimResults = true
      recog.continuous = false
      recog.onresult = (e) => {
        let interim = ''
        let final = ''
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i]
          if (r.isFinal) final += r[0].transcript
          else interim += r[0].transcript
        }
        if (interim && onInterim) onInterim(interim)
        if (final) {
          onFinal(final.trim())
        }
      }
      recog.onerror = () => setListening(false)
      recog.onend = () => setListening(false)
      try {
        recog.start()
        setListening(true)
        return true
      } catch {
        setListening(false)
        return false
      }
    },
    [],
  )

  const stopListening = useCallback(() => {
    try {
      recogRef.current?.stop()
    } catch {
      /* ignore */
    }
    setListening(false)
  }, [])

  useEffect(() => {
    return () => {
      try {
        recogRef.current?.abort?.()
      } catch {
        /* ignore */
      }
      if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    }
  }, [])

  return { voiceOn, setVoiceOn, listening, speaking, supported, speak, stopSpeaking, listen, stopListening }
}

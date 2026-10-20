export type ParsedResume = {
  full_name: string
  email: string
  phone: string
  summary: string
  skills: string[]
  projects: Array<{
    name: string
    description: string
    tech_stack: string[]
    impact: string
    highlights: string[]
  }>
  education: Array<{
    institution: string
    degree: string
    field: string
    dates: string
    gpa?: string | null
  }>
  experience: Array<{
    company: string
    title: string
    dates: string
    bullets: string[]
  }>
  achievements: string[]
  inferred_seniority: string
}

export type Resume = {
  id: string
  original_filename: string
  parse_status: string
  parsed?: ParsedResume | null
  created_at: string
}

export type Company = {
  id: string
  name: string
  difficulty_default: string
  focus_areas: string[]
  persona: Record<string, string>
}

export type Role = {
  id: string
  company_id: string
  title: string
  level: string
  skills_focus: string[]
}

export type InterviewRound = {
  index: number
  name: string
  type: string
  duration_minutes: number
  status: string
  score?: number | null
  feedback: string
}

export type Turn = {
  id: string
  turn_index: number
  question_type: string
  question_text: string
  answer_text?: string | null
  retrieval_ids: string[]
}

export type Interview = {
  id: string
  status: string
  company_id: string
  role_id: string
  current_turn: number
  max_turns: number
  duration_minutes: number
  elapsed_seconds: number
  current_round: number
  rounds: InterviewRound[]
  mode: string
  turns: Turn[]
  started_at?: string | null
  completed_at?: string | null
  created_at?: string | null
}

export type DimensionScore = {
  score: number
  rationale: string
  evidence: string[]
}

export type Evaluation = {
  id: string
  session_id: string
  overall_score: number
  hiring_signal: string
  dimensions: Record<string, DimensionScore>
  summary: string
  recommendations: string[]
  model: string
  created_at: string
  rounds: InterviewRound[]
}

export type Settings = {
  chat_model: string
  embedding_model: string
  has_api_key: boolean
  max_interview_turns: number
}

export type ModelOption = {
  id: string
  name: string
  context_length?: number | null
}

export type KeyVerification = {
  valid: boolean
  label?: string | null
  error?: string | null
}

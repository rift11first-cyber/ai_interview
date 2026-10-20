import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { OnboardingGate } from '@/components/OnboardingGate'
import { HomePage } from '@/pages/HomePage'
import { ResumePage } from '@/pages/ResumePage'
import { SetupPage } from '@/pages/SetupPage'
import { InterviewPage } from '@/pages/InterviewPage'
import { EvaluationPage } from '@/pages/EvaluationPage'
import { HistoryPage } from '@/pages/HistoryPage'
import { SettingsPage } from '@/pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <OnboardingGate />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/resume" element={<ResumePage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/interview/:id" element={<InterviewPage />} />
          <Route path="/evaluation/:id" element={<EvaluationPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  )
}

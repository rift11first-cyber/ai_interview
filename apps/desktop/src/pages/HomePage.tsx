import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function HomePage() {
  return (
    <section className="relative flex h-full min-h-0 w-full items-center overflow-hidden">
      <div className="pointer-events-none absolute inset-y-0 left-0 hidden w-px bg-sky-300/25 lg:block" />
      <div className="grid w-full items-center gap-10 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)] lg:gap-16">
        <div className="relative max-w-4xl space-y-7 lg:pl-10">
          <div className="flex items-center gap-3 text-[0.65rem] font-semibold uppercase tracking-[0.28em] text-sky-300/80">
            <span className="h-px w-8 bg-sky-300" />
            InterviewIQ · Practice studio
          </div>
          <h1
            className="max-w-4xl text-[clamp(3.4rem,8vw,7.7rem)] leading-[0.86] tracking-[-0.055em] text-sky-50"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Practice with<br className="hidden sm:block" /> purpose.
          </h1>
          <p className="max-w-lg text-base leading-relaxed text-sky-100/60 sm:text-lg">
            Role-specific mock interviews, honest feedback, and a clearer path to your next offer.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Link to="/setup"><Button size="lg" className="rounded-full px-7">Start an interview <span aria-hidden="true">↗</span></Button></Link>
            <Link to="/resume"><Button size="lg" variant="ghost" className="rounded-full px-7 text-sky-200 hover:bg-black hover:text-sky-100">Add your resume</Button></Link>
          </div>
          <p className="pt-2 text-xs tracking-wide text-sky-100/35">No preparation theatre. Just useful practice.</p>
        </div>

        <aside className="hidden border border-sky-300/25 p-6 lg:block">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-sky-300/75">Your session</p>
            <span className="h-2 w-2 rounded-full border border-sky-300" />
          </div>
          <div className="space-y-5 py-6">
            <p className="max-w-xs text-sm leading-6 text-sky-100/55">
              Sara adapts every conversation to your level, role, and the experience you bring.
            </p>
            <div className="grid grid-cols-3 gap-3 border-y border-white/10 py-5">
              <Metric value="45" label="minutes" />
              <Metric value="03" label="rounds" />
              <Metric value="01" label="clear read" />
            </div>
          </div>
          <Link to="/history" className="group inline-flex items-center gap-2 text-sm text-sky-300 underline-offset-4 hover:underline">
            View your progress <span className="transition-transform group-hover:translate-x-1" aria-hidden="true">→</span>
          </Link>
        </aside>
      </div>
    </section>
  )
}

function Metric({ value, label }: { value: string; label: string }) {
  return <div><p className="text-2xl font-medium tracking-[-0.04em] text-sky-100">{value}</p><p className="mt-1 text-[0.65rem] uppercase tracking-[0.13em] text-sky-100/40">{label}</p></div>
}

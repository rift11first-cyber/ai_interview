import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

const links = [
  { to: '/', label: 'Home' },
  { to: '/resume', label: 'Resume' },
  { to: '/setup', label: 'Interview' },
  { to: '/history', label: 'History' },
  { to: '/settings', label: 'Settings' },
]

function BackendStatus() {
  const [online, setOnline] = useState<boolean | null>(null)
  useEffect(() => {
    let alive = true
    async function check() {
      try {
        await api.health()
        if (alive) setOnline(true)
      } catch {
        if (alive) setOnline(false)
      }
    }
    check()
    const t = setInterval(check, 10000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])
  if (online !== false) {
    return online ? (
      <span className="block h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_12px_rgba(110,231,183,0.8)]" title="Backend online">
      </span>
    ) : null
  }
  return (
    <span
      className="block h-2 w-2 rounded-full bg-red-400"
      title="Start it with: cd backend && uv run interviewiq"
    >
    </span>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [navVisible, setNavVisible] = useState(true)
  const { pathname } = useLocation()
  const isHome = pathname === '/'

  useEffect(() => {
    let previousY = window.scrollY
    const handleScroll = () => {
      const currentY = window.scrollY
      setNavVisible(currentY < 24 || currentY < previousY)
      previousY = currentY
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <div className="min-h-screen bg-black text-sky-100">
      <header className={cn('fixed left-0 right-0 top-3 z-20 mx-auto max-w-4xl px-2 transition-transform duration-300', navVisible ? 'translate-y-0' : '-translate-y-[calc(100%+2rem)]')}>
        <div className="flex items-center justify-center rounded-full border border-white/10 bg-black/90 px-2 py-2 shadow-2xl shadow-sky-950/30 backdrop-blur-xl">
          <nav className="mx-auto flex flex-wrap items-center justify-center gap-0.5">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-full px-2.5 py-1.5 text-xs no-underline transition',
                    isActive
                      ? 'border border-sky-300 bg-black font-medium text-sky-200'
                      : 'text-sky-100/60 hover:bg-black hover:text-sky-100',
                  )
                }
              >
                {l.label}
              </NavLink>
            ))}
            <span className="ml-2 border-l border-white/10 pl-2">
              <BackendStatus />
            </span>
          </nav>
        </div>
      </header>
      <main
        className={cn(
          'mx-auto flex w-full max-w-6xl justify-center px-6',
          isHome
            ? 'h-[100dvh] overflow-hidden pb-6 pt-24 sm:px-8 sm:pt-28'
            : 'min-h-screen pb-12 pt-32',
        )}
      >
        {children}
      </main>
    </div>
  )
}

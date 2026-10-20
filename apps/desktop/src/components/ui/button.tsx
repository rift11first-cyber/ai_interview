import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
}

export function Button({
  className,
  variant = 'primary',
  size = 'md',
  ...props
}: Props) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:opacity-50 disabled:pointer-events-none',
        variant === 'primary' &&
          'border border-sky-300 bg-black text-sky-200 hover:bg-black/80 shadow-sm',
        variant === 'secondary' &&
          'border border-white/15 bg-black text-sky-100 hover:bg-black/80',
        variant === 'ghost' && 'bg-transparent text-sky-100/60 hover:bg-black/80 hover:text-sky-100',
        variant === 'danger' && 'border border-red-400 bg-black text-sky-200 hover:bg-black/80',
        size === 'sm' && 'h-9 px-3 text-sm',
        size === 'md' && 'h-11 px-4 text-sm',
        size === 'lg' && 'h-12 px-6 text-base',
        className,
      )}
      {...props}
    />
  )
}

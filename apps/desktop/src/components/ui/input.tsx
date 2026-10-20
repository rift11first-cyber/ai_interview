import type { InputHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-11 w-full rounded-xl border border-white/15 bg-black px-3 text-sm text-sky-100 placeholder:text-sky-100/25 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-300/15',
        className,
      )}
      {...props}
    />
  )
}

import type { TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'min-h-32 w-full rounded-xl border border-white/15 bg-black px-3 py-2.5 text-sm text-sky-100 placeholder:text-sky-100/25 outline-none focus:border-sky-300 focus:ring-2 focus:ring-sky-300/15 resize-y',
        className,
      )}
      {...props}
    />
  )
}

import * as React from "react"
import { cn } from "@/lib/utils"

interface AsanaLogoProps {
  /** Height in px. Width scales proportionally. */
  height?: number
  className?: string
}

/**
 * Asana lockup: three-coral-dot mark + "asana" wordmark.
 */
export function AsanaLogo({ height = 20, className }: AsanaLogoProps) {
  const width = Math.round((96 / 24) * height)
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 96 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Asana"
      role="img"
      className={cn("shrink-0 text-foreground", className)}
    >
      <circle cx="12" cy="16" r="4.5" fill="#F06A6A" />
      <circle cx="6" cy="7.5" r="4.5" fill="#F06A6A" />
      <circle cx="18" cy="7.5" r="4.5" fill="#F06A6A" />
      <text
        x="30"
        y="17"
        fontFamily="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
        fontSize="15"
        fontWeight="700"
        letterSpacing="-0.5"
        fill="currentColor"
      >
        asana
      </text>
    </svg>
  )
}

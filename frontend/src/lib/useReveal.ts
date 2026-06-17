"use client"

import { useEffect, useRef } from "react"

/**
 * Adds `is-in` to the element once it scrolls into view (one-shot), pairing with
 * the `.reveal` CSS. Respects prefers-reduced-motion (reveals immediately).
 */
export function useReveal<T extends HTMLElement = HTMLDivElement>(options?: IntersectionObserverInit) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      el.classList.add("is-in")
      return
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add("is-in")
            io.unobserve(e.target)
          }
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.12, ...options },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [options])
  return ref
}

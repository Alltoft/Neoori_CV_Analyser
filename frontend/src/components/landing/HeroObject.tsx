"use client"

import { useEffect, useRef, useState } from "react"
import { cn } from "@/lib/utils"
import { canRunLive3D, readDevice } from "@/lib/live-3d"

export interface Still {
  /** Path without extension: `${src}.avif` and `${src}.webp` exist. */
  src: string
  width: number
  height: number
}

/** A landing's 3D object, still first (landings spec, decisions 24–26). The
 *  server renders a still image of the exact scene. After `load` and an idle
 *  moment, on a capable desktop, the live three.js scene fades in over it;
 *  any failure, or the window narrowing to a phone width, keeps the still. */
export function HeroObject({
  scene,
  desktop,
  phone,
  pointerAreaId,
  className,
}: {
  scene: "sheet" | "mark"
  desktop: Still
  phone: Still
  pointerAreaId: string
  className?: string
}) {
  const host = useRef<HTMLDivElement>(null)
  const [live, setLive] = useState(false)

  useEffect(() => {
    let disposed = false
    let controller: { dispose(): void } | null = null
    const narrow = window.matchMedia("(max-width: 900px)")

    const stop = () => {
      controller?.dispose()
      controller = null
      setLive(false)
    }
    const start = async () => {
      if (disposed || controller || !host.current || !canRunLive3D(readDevice(window))) return
      try {
        const { mountScene } = await import("./scenes")
        if (disposed || !host.current) return
        controller = mountScene(scene, host.current, {
          layout: "desktop",
          pointerArea: document.getElementById(pointerAreaId),
        })
        setLive(true)
      } catch (error) {
        console.error("neoori: the live 3D did not start; the still image stays.", error)
        stop()
      }
    }
    const kick = () => {
      if ("requestIdleCallback" in window) window.requestIdleCallback(() => void start(), { timeout: 2000 })
      else setTimeout(() => void start(), 800)
    }
    const onNarrow = () => {
      if (narrow.matches) stop()
    }

    narrow.addEventListener("change", onNarrow)
    if (document.readyState === "complete") kick()
    else window.addEventListener("load", kick, { once: true })
    return () => {
      disposed = true
      narrow.removeEventListener("change", onNarrow)
      window.removeEventListener("load", kick)
      controller?.dispose()
    }
  }, [scene, pointerAreaId])

  return (
    <div ref={host} className={cn("lp-3d", live && "is-live", className)} aria-hidden="true">
      <picture>
        <source media="(min-width: 901px)" type="image/avif" srcSet={`${desktop.src}.avif`} />
        <source media="(min-width: 901px)" type="image/webp" srcSet={`${desktop.src}.webp`} />
        <source type="image/avif" srcSet={`${phone.src}.avif`} />
        <img
          className="lp-still"
          src={`${phone.src}.webp`}
          alt=""
          width={phone.width}
          height={phone.height}
          decoding="async"
          fetchPriority="high"
        />
      </picture>
    </div>
  )
}

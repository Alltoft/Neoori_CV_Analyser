"use client"

import Image from "next/image"
import { useState } from "react"
import { cn } from "@/lib/utils"
import { InfinityMark } from "@/components/brand/Logo"

/**
 * Brand-safe image. Fills its (sized) parent via object-cover. If the file is
 * missing (e.g. not generated yet) it degrades to a warm brand placeholder with
 * the ring motif — never a broken-image icon, never a collapsed layout.
 *
 * The wrapper must be given a size by the caller (aspect-* or a height class).
 */
export function Photo({
  src,
  alt,
  className,
  imgClassName,
  sizes = "100vw",
  priority = false,
  rounded = "rounded-2xl",
  overlay = false,
}: {
  src: string
  alt: string
  className?: string
  imgClassName?: string
  sizes?: string
  priority?: boolean
  rounded?: string | false
  /** dark gradient scrim for text legibility on top of the photo */
  overlay?: boolean
}) {
  const [failed, setFailed] = useState(false)
  return (
    <div className={cn("relative overflow-hidden bg-mesh", rounded || "", className)}>
      {!failed ? (
        <Image
          src={src}
          alt={alt}
          fill
          sizes={sizes}
          priority={priority}
          className={cn("object-cover", imgClassName)}
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="absolute inset-0 grid place-items-center">
          <InfinityMark className="text-6xl opacity-25" />
        </div>
      )}
      {overlay && (
        <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-navy/55 via-navy/10 to-transparent" />
      )}
    </div>
  )
}

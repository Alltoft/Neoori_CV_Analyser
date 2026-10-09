"use client"

import { useParams, useRouter } from "next/navigation"
import { RunProgress } from "@/components/analyse/RunProgress"
import { api } from "@/lib/api"
import type { Analysis } from "@/types"

export default function EnCoursPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  return (
    <RunProgress
      load={() => api.get<{ analysis: Analysis }>(`/analyses/${id}`).then((r) => r.analysis)}
      onDone={() => router.push(`/analyse/${id}/rapport`)}
      mailed
      onRestart={() => router.push("/analyse/nouveau")}
      onRelaunch={() => api.post(`/analyses/${id}/relaunch`)}
    />
  )
}

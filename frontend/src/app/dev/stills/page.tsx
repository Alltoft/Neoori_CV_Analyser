import { notFound } from "next/navigation"
import { StillsStudio } from "./StillsStudio"

// Dev only (landings spec, decision 26): renders the landings' still images
// and share images from the 3D scenes and saves them into public/. A 404
// outside `next dev`.
export default function StillsPage() {
  if (process.env.NODE_ENV !== "development") notFound()
  return <StillsStudio />
}

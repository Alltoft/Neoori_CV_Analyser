import type { MetadataRoute } from "next"
import { robotsFor } from "@/lib/seo"
import { currentSite } from "@/lib/site-server"

// One robots.txt per host (landings spec, decision 14). Reading the host
// makes this route per request rather than cached at build time.
export default async function robots(): Promise<MetadataRoute.Robots> {
  const { app, settings } = await currentSite()
  return robotsFor(app, settings)
}

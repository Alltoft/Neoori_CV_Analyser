import type { MetadataRoute } from "next"
import { sitemapFor } from "@/lib/seo"
import { currentSite } from "@/lib/site-server"

// One sitemap.xml per host (landings spec, decision 14).
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const { app, settings } = await currentSite()
  return sitemapFor(app, settings)
}

import { headers } from "next/headers"
import { appOfHost, settingsFromEnv, type Site } from "./site"

/** This request's app and the settings, read at request time (subdomain
 *  split spec, decisions 21 and 24): DOMAIN comes from the container's
 *  environment, so changing it needs no rebuild. Server components only. */
export async function currentSite(): Promise<Site> {
  const settings = settingsFromEnv(process.env)
  return { settings, app: appOfHost((await headers()).get("host"), settings.domain) }
}

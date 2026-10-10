import { mkdir, writeFile } from "node:fs/promises"
import path from "node:path"

const NAME = /^(cv|voyage)-(desktop|phone)\.png$|^og-(cv|voyage)\.png$/

/** Dev only (landings spec, decision 26): writes one PNG rendered by
 *  /dev/stills into public/landing/ (stills) or public/og/ (share images).
 *  Answers 404 anywhere but `next dev`. */
export async function POST(request: Request): Promise<Response> {
  if (process.env.NODE_ENV !== "development") return new Response(null, { status: 404 })
  const name = new URL(request.url).searchParams.get("name") ?? ""
  if (!NAME.test(name)) return new Response("unexpected name", { status: 400 })
  const share = name.startsWith("og-")
  const dir = path.join(process.cwd(), "public", share ? "og" : "landing")
  const file = path.join(dir, share ? name.slice(3) : name)
  await mkdir(dir, { recursive: true })
  await writeFile(file, Buffer.from(await request.arrayBuffer()))
  return Response.json({ saved: path.relative(process.cwd(), file) })
}

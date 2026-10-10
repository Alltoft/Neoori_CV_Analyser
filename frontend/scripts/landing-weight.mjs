// What a first visit to one page downloads, compressed (landings spec,
// decision 30): HTML, CSS and JS gzipped as the server sends them, plus the
// preloaded fonts and the stills the HTML names. The live 3D chunk is not
// counted: it loads after the page, on capable desktops only. Neither are
// pictures served through /_next/image (the root landing's photos): their
// size depends on the screen, so the script reports how many, not their weight.
// Usage: node scripts/landing-weight.mjs http://127.0.0.1:3000 cv.neoori.localhost
// (the host goes in a header: Node does not resolve *.localhost on macOS).
import http from "node:http"
import { gzipSync } from "node:zlib"

const [base, host] = process.argv.slice(2)
if (!base || !host) throw new Error("usage: landing-weight.mjs <server origin> <host name>")

function get(path, accept = "*/*") {
  return new Promise((resolve, reject) => {
    const request = http.request(new URL(path, base), { headers: { host, accept } }, (response) => {
      if (response.statusCode !== 200) {
        response.resume()
        reject(new Error(`${response.statusCode} ${path}`))
        return
      }
      const chunks = []
      response.on("data", (chunk) => chunks.push(chunk))
      response.on("end", () => resolve(Buffer.concat(chunks)))
    })
    request.on("error", reject)
    request.end()
  })
}

const html = (await get("/", "text/html")).toString("utf8")
const assets = new Set()
for (const m of html.matchAll(/(?:src|href)="(\/_next\/static\/[^"]+\.(?:js|css))"/g)) assets.add(m[1])
// Next.js names the preloaded fonts in React's flight data (`:HL[…]`) and in a
// Link header, never in a <link> tag: take every font file the page names.
for (const m of html.matchAll(/\/_next\/static\/media\/[^"\\\s]+\.woff2/g)) assets.add(m[0])
const images = new Set()
for (const m of html.matchAll(/<source[^>]*media="\(min-width: 901px\)"[^>]*type="image\/avif"[^>]*srcSet="([^"]+)"/gi)) images.add(m[1])
for (const m of html.matchAll(/<img[^>]*\ssrc="(\/(?!_next)[^"]+)"/gi)) images.add(m[1])
const resized = html.match(/<img[^>]*\ssrc="\/_next\/image/gi)?.length ?? 0

const totals = { html: gzipSync(Buffer.from(html)).length, js: 0, css: 0, fonts: 0, images: 0 }
for (const path of assets) {
  const body = await get(path)
  if (path.endsWith(".js")) totals.js += gzipSync(body).length
  else if (path.endsWith(".css")) totals.css += gzipSync(body).length
  else totals.fonts += body.length
}
for (const path of images) totals.images += (await get(path, "image/avif,image/webp,*/*")).length
const kb = (n) => `${(n / 1024).toFixed(0)} KB`
const total = Object.values(totals).reduce((a, b) => a + b, 0)
const note = resized ? `, plus ${resized} /_next/image pictures not counted` : ""
console.log(host, Object.fromEntries(Object.entries(totals).map(([k, v]) => [k, kb(v)])), `total ${kb(total)}${note}`)

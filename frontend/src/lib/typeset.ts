const NBSP = " "
const NNBSP = " "

/** French typography for UI copy (landings spec, decision 31): a no-break
 *  space before « : » and inside guillemets, a narrow no-break space before
 *  « ; ! ? », and a no-break space between a number and its unit. Copy files
 *  are written with plain spaces; this function sets them. */
export function fr(text: string): string {
  return text
    .replace(/ +:/g, `${NBSP}:`)
    .replace(/ +([;!?])/g, `${NNBSP}$1`)
    .replace(/« +/g, `«${NBSP}`)
    .replace(/ +»/g, `${NBSP}»`)
    .replace(/(\d) +(€|Mo|%)/g, `$1${NBSP}$2`)
}

/** fr() on every string inside a copy object; anything else is kept as is. */
export function typeset<T>(value: T): T {
  if (typeof value === "string") return fr(value) as T
  if (Array.isArray(value)) return value.map((item) => typeset(item)) as T
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, typeset(item)])) as T
  }
  return value
}

let pending: (() => void) | null = null

/** Resolves once the next client navigation has committed (NavigationSettled
 *  calls settleNavigation), or after `timeoutMs`: a View Transition must never
 *  wait on a navigation that does not come (landings spec, decision 22). */
export function waitForNavigation(timeoutMs = 3000): Promise<void> {
  pending?.()
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(timer)
      if (pending === done) pending = null
      resolve()
    }
    const timer = setTimeout(done, timeoutMs)
    pending = done
  })
}

/** Releases the wipe that is waiting, if any. */
export function settleNavigation(): void {
  const done = pending
  pending = null
  done?.()
}

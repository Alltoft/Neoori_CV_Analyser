const BASE = process.env.NEXT_PUBLIC_API_URL ?? ""

type ApiOptions = RequestInit & { skipRedirect?: boolean }

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { skipRedirect, ...init } = options

  const isFormData = init.body instanceof FormData
  let res: Response
  try {
    res = await fetch(`${BASE}/api${path}`, {
      ...init,
      credentials: "include",
      // FormData: let browser set Content-Type with correct multipart boundary
      headers: isFormData
        ? { ...(init.headers as Record<string, string>) }
        : { "Content-Type": "application/json", ...(init.headers as Record<string, string>) },
    })
  } catch {
    // Network failure — most often the free-tier backend waking from sleep
    throw new ApiError(0, "Connexion au serveur impossible. Il démarre peut-être — réessayez dans 30 secondes.")
  }

  if (res.status === 401 && !skipRedirect && typeof window !== "undefined") {
    window.location.href = "/connexion"
    return null as T
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const fallback =
      res.status === 429
        ? "Trop de requêtes — patientez une minute puis réessayez."
        : res.status >= 502 && res.status <= 504
          ? "Le serveur démarre ou est temporairement indisponible. Réessayez dans 30 secondes."
          : "Erreur inattendue."
    throw new ApiError(res.status, body.error ?? body.message ?? fallback)
  }

  const text = await res.text()
  return text ? JSON.parse(text) : ({} as T)
}

export const api = {
  get:    <T>(path: string, opts?: ApiOptions) =>
    request<T>(path, { method: "GET", ...opts }),

  post:   <T>(path: string, body?: unknown, opts?: ApiOptions) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body), ...opts }),

  put:    <T>(path: string, body?: unknown, opts?: ApiOptions) =>
    request<T>(path, { method: "PUT",  body: JSON.stringify(body), ...opts }),

  delete: <T>(path: string, opts?: ApiOptions) =>
    request<T>(path, { method: "DELETE", ...opts }),

  /** Multipart upload (no Content-Type header — browser sets boundary) */
  upload: <T>(path: string, formData: FormData, opts?: ApiOptions) => {
    const { headers, ...rest } = opts ?? {}
    return request<T>(path, { method: "POST", body: formData,
      headers: { ...(headers as Record<string, string>) }, ...rest })
  },
}

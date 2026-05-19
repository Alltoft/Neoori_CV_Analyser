const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5001"

type ApiOptions = RequestInit & { skipRedirect?: boolean }

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { skipRedirect, ...init } = options

  const isFormData = init.body instanceof FormData
  const res = await fetch(`${BASE}/api${path}`, {
    ...init,
    credentials: "include",
    // FormData: let browser set Content-Type with correct multipart boundary
    headers: isFormData
      ? { ...(init.headers as Record<string, string>) }
      : { "Content-Type": "application/json", ...(init.headers as Record<string, string>) },
  })

  if (res.status === 401 && !skipRedirect && typeof window !== "undefined") {
    window.location.href = "/connexion"
    return null as T
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.error ?? body.message ?? "Erreur inattendue.")
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

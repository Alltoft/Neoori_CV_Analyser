"use client"

import {
  createContext, useContext, useEffect, useState, useCallback,
  type ReactNode,
} from "react"
import { api, ApiError } from "./api"
import type { User } from "@/types"

interface AuthContextValue {
  user: User | null
  loading: boolean
  /** Resolves with the signed-in user, so a caller can route by role. */
  login:    (email: string, password: string) => Promise<User>
  /** Creates the account and mails the confirmation link. No session: the
   *  person signs in from the link, with their password. */
  register: (email: string, password: string, seed?: ProfileSeed, next?: string | null) => Promise<{ mail_sent: boolean }>
  logout:   () => Promise<void>
  refresh:  () => Promise<void>
}

/** What signup seeds the Profil de base with. The two fields session_lock has
 *  demanded before session 1 since the voyage shipped — collected here so the
 *  person never meets a form in the middle of the journey. `consent` is the CGV
 *  box the form already shows; nothing is stored without it. */
export interface ProfileSeed {
  prenom: string
  tranche_age: string
  consent: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await api.get<{ user: User }>("/auth/me", { skipRedirect: true })
      setUser(data.user)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const login = async (email: string, password: string) => {
    // skipRedirect: a 401 here is « Identifiants incorrects. » and a 403 is an
    // unconfirmed address — both for the page to show. Without it api.ts
    // reloaded /connexion on a wrong password and the message was lost.
    const data = await api.post<{ user: User }>("/auth/login", { email, password }, { skipRedirect: true })
    setUser(data.user)
    return data.user
  }

  const register = async (email: string, password: string, seed?: ProfileSeed, next?: string | null) => {
    const data = await api.post<{ user: User; mail_sent: boolean }>(
      "/auth/register",
      { email, password, ...seed, next: next ?? undefined },
      { skipRedirect: true },
    )
    return { mail_sent: data.mail_sent }
  }

  const logout = async () => {
    await api.post("/auth/logout")
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider")
  return ctx
}

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
  register: (email: string, password: string, seed?: ProfileSeed) => Promise<void>
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
    const data = await api.post<{ user: User }>("/auth/login", { email, password })
    setUser(data.user)
    return data.user
  }

  const register = async (email: string, password: string, seed?: ProfileSeed) => {
    const data = await api.post<{ user: User }>("/auth/register", { email, password, ...seed })
    setUser(data.user)
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

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
  login:    (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout:   () => Promise<void>
  refresh:  () => Promise<void>
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
  }

  const register = async (email: string, password: string) => {
    const data = await api.post<{ user: User }>("/auth/register", { email, password })
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

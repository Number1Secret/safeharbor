"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/utils/api";

interface User {
  id: string;
  email: string;
  name: string;
  organization_id: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    org_name: string;
    ein: string;
    email: string;
    password: string;
    name: string;
  }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function decodeJWT(token: string): Record<string, any> | null {
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

function tokenToUser(token: string): User | null {
  const payload = decodeJWT(token);
  if (!payload) return null;
  return {
    id: payload.sub || "",
    email: payload.email || "",
    name: payload.name || "",
    organization_id: payload.org_id || "",
    role: payload.role || "viewer",
  };
}

const TOKEN_KEY = "safeharbor_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  // Initialize from stored token
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      const decoded = tokenToUser(token);
      if (decoded) {
        setUser(decoded);
      } else {
        localStorage.removeItem(TOKEN_KEY);
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await api.login(email, password);
      localStorage.setItem(TOKEN_KEY, response.access_token);
      const decoded = tokenToUser(response.access_token);
      setUser(decoded);
      router.push("/dashboard");
    },
    [router]
  );

  const register = useCallback(
    async (data: {
      org_name: string;
    ein: string;
      email: string;
      password: string;
      name: string;
    }) => {
      const response = await api.register(data);
      localStorage.setItem(TOKEN_KEY, response.access_token);
      const decoded = tokenToUser(response.access_token);
      setUser(decoded);
      router.push("/dashboard");
    },
    [router]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    router.push("/login");
  }, [router]);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      register,
      logout,
    }),
    [user, isLoading, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

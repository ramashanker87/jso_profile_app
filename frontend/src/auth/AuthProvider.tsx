import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import * as client from "./client";
import type { Challenge } from "./client";
interface Auth {
  user: string | null;
  loading: boolean;
  expired: boolean;
  authorized: boolean;
  authError: string;
  login(username: string, password: string): Promise<Challenge | null>;
  confirm(
    answer: string,
    attributes: Record<string, string>,
  ): Promise<Challenge | null>;
  logout(): Promise<void>;
}
const Context = createContext<Auth | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<string | null>(null),
    [loading, setLoading] = useState(true),
    [expired, setExpired] = useState(false),
    [authorized, setAuthorized] = useState(false),
    [authError, setAuthError] = useState("");
  useEffect(() => {
    let active = true;
    let refreshVersion = 0;
    const refresh = async (failed = false) => {
      const version = ++refreshVersion;
      try {
        const value = await client.currentUser();
        const allowed = value ? await client.hasAppAccess() : false;
        if (active && version === refreshVersion) {
          setUser(value);
          setAuthorized(allowed);
          setAuthError(
            failed ? "Google sign-in was not completed. Please try again." : "",
          );
        }
      } catch {
        if (active && version === refreshVersion) {
          setUser(null);
          setAuthorized(false);
          setAuthError("Unable to complete sign-in. Please try again.");
        }
      } finally {
        if (active && version === refreshVersion) setLoading(false);
      }
    };
    const unsubscribe = client.onAuthChange(refresh);
    void refresh();
    const expire = () => {
      ++refreshVersion;
      setUser(null);
      setAuthorized(false);
      setExpired(true);
    };
    window.addEventListener("session-expired", expire);
    return () => {
      active = false;
      unsubscribe();
      window.removeEventListener("session-expired", expire);
    };
  }, []);
  const value: Auth = {
    user,
    loading,
    expired,
    authorized,
    authError,
    login: async (username, password) => {
      const result = await client.login(username, password);
      if (!result) {
        setAuthorized(await client.hasAppAccess());
        setUser(await client.currentUser());
        setExpired(false);
        setAuthError("");
      }
      return result;
    },
    confirm: async (answer, attributes) => {
      const result = await client.challenge(answer, attributes);
      if (!result) {
        setAuthorized(await client.hasAppAccess());
        setUser(await client.currentUser());
        setExpired(false);
        setAuthError("");
      }
      return result;
    },
    logout: async () => {
      await client.logout();
      setUser(null);
      setAuthorized(false);
      setExpired(false);
    },
  };
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}

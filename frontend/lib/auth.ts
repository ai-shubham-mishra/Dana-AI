"use client";

import { useSyncExternalStore } from "react";

export const ACCESS_TOKEN_KEY = "dana.accessToken";
const AUTH_EVENT = "dana-auth-changed";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token.trim());
  window.dispatchEvent(new Event(AUTH_EVENT));
}

export function clearAccessToken() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.dispatchEvent(new Event(AUTH_EVENT));
}

function subscribe(onChange: () => void) {
  window.addEventListener(AUTH_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(AUTH_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useAccessToken(): string | null {
  return useSyncExternalStore(subscribe, getAccessToken, () => null);
}

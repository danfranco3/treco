const TOKEN_KEY = "treco_auth_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return Date.now() / 1000 > payload.exp;
  } catch {
    return true;
  }
}

export async function refreshToken(current: string): Promise<string | null> {
  try {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { Authorization: `Bearer ${current}` },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token: string };
    setToken(data.access_token);
    return data.access_token;
  } catch {
    return null;
  }
}

export async function getValidToken(): Promise<string | null> {
  const token = getToken();
  if (!token) return null;
  if (!isTokenExpired(token)) return token;

  const fresh = await refreshToken(token);
  if (!fresh) {
    clearToken();
    return null;
  }
  return fresh;
}

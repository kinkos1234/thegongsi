const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8888";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  company: (ticker: string) => request(`/api/companies/${ticker}`),
  disclosures: (ticker?: string) =>
    request(`/api/disclosures/${ticker ? `?ticker=${ticker}` : ""}`),
  generateMemo: (ticker: string, token?: string) =>
    request("/api/memos/generate", {
      method: "POST",
      body: JSON.stringify({ ticker }),
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    }),
};

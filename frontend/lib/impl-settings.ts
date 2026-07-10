export interface ImplSettings {
  model: string;
  system_prompt: string;
}

export const DEFAULT_IMPL: ImplSettings = {
  model: "claude-sonnet-5",
  system_prompt: "",
};

const KEY = "treco_impl_settings";

export function loadImplSettings(): ImplSettings {
  if (typeof window === "undefined") return DEFAULT_IMPL;
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULT_IMPL, ...JSON.parse(raw) } : DEFAULT_IMPL;
  } catch {
    return DEFAULT_IMPL;
  }
}

export function saveImplSettings(s: ImplSettings): void {
  localStorage.setItem(KEY, JSON.stringify(s));
}

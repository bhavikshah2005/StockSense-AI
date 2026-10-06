export function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  const fallback = "http://localhost:8000";
  const raw = typeof configured === "string" && configured.length > 0 ? configured : fallback;
  const url = new URL(raw);
  if (typeof window !== "undefined") {
    const pageHost = window.location.hostname;
    const apiHost = url.hostname;
    const localHosts = new Set(["localhost", "127.0.0.1"]);
    if (localHosts.has(pageHost) && localHosts.has(apiHost)) {
      url.hostname = pageHost;
    }
  }
  return url.origin;
}

// Root paths in the normal app; Supervisor's session-specific prefix inside Home Assistant.
export function basePath(): string {
  if (typeof document === "undefined") return "";
  return document.querySelector<HTMLMetaElement>('meta[name="runway-base-path"]')?.content ?? "";
}
export function appPath(path: string): string {
  const base = basePath();
  return base && path.startsWith("/") && !path.startsWith("//") && !path.startsWith(base + "/") ? base + path : path;
}

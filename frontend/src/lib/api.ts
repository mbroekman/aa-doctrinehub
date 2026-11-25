import type {
  Doctrine,
  FittingDetail,
  FittingSummary,
  RemoteScrapeImportResult,
  RemoteScrapePreview,
  SyncSettings,
} from "@/types";

export interface SpaConfig {
  apiPrefix: string;
  appName: string;
  canManage: boolean;
  csrfToken: string;
}

export function getSpaConfig(): SpaConfig {
  const root = document.getElementById("aa-doctrinehub-spa");
  const doctrinesUrl = root?.dataset.apiPrefix || "/doctrines/api/v1/doctrines/";
  return {
    apiPrefix: doctrinesUrl.replace(/doctrines\/?$/, ""),
    appName: root?.dataset.appName || "Doctrines",
    canManage: root?.dataset.canManage === "true",
    csrfToken: root?.dataset.csrfToken || "",
  };
}

const config = getSpaConfig();

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${config.apiPrefix}${path}`, {
    credentials: "same-origin",
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": config.csrfToken,
      ...(init.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((data as { error?: string }).error || `Request failed (${response.status})`);
  }
  return data as T;
}

export const api = {
  doctrines: () => request<{ doctrines: Doctrine[] }>("doctrines/").then((d) => d.doctrines),
  fittings: () => request<{ fittings: FittingSummary[] }>("fittings/").then((d) => d.fittings),
  fitting: (id: number) => request<FittingDetail>(`fittings/${id}/`),
  importFitting: (eft: string) =>
    request<FittingSummary>("fittings/import/", { method: "POST", body: JSON.stringify({ eft }) }),
  syncSettings: () => request<SyncSettings>("settings/sync/"),
  saveSyncSettings: (changes: Partial<SyncSettings>) =>
    request<SyncSettings>("settings/sync/", { method: "POST", body: JSON.stringify(changes) }),
  runFittingsSync: () =>
    request<SyncSettings & { queued: boolean }>("settings/sync/run/", { method: "POST" }),
  remoteScrapePreview: (payload: {
    base_url: string;
    sessionid: string;
    include_standalone_fits: boolean;
    include_categories: boolean;
  }) =>
    request<RemoteScrapePreview>("settings/remote-scrape/", {
      method: "POST",
      body: JSON.stringify({ ...payload, mode: "preview" }),
    }),
  remoteScrapeImport: (payload: {
    base_url: string;
    sessionid: string;
    include_standalone_fits: boolean;
    include_categories: boolean;
  }) =>
    request<RemoteScrapeImportResult>("settings/remote-scrape/", {
      method: "POST",
      body: JSON.stringify({ ...payload, mode: "import" }),
    }),
};

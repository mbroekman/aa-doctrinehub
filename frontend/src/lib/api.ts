import type {
  AuditLogEntry,
  ComplianceOverviewResponse,
  ComplianceRule,
  Doctrine,
  EligibilityStatusResponse,
  FittingDetail,
  FittingEligibilityResponse,
  FittingSummary,
  HangarShipMatch,
  IndustryOrderResult,
  NotificationSettings,
  PendingApprovalItem,
  RemoteScrapeImportResult,
  RemoteScrapePreview,
  RemoteScrapePurgeResult,
  SrpCompareResult,
  SyncSettings,
} from "@/types";

export interface SpaConfig {
  apiPrefix: string;
  appName: string;
  canManage: boolean;
  canViewCompliance: boolean;
  canManageRules: boolean;
  linkCharacterUrl: string;
  csrfToken: string;
}

export function getSpaConfig(): SpaConfig {
  const root = document.getElementById("aa-doctrinehub-spa");
  const doctrinesUrl = root?.dataset.apiPrefix || "/doctrines/api/v1/doctrines/";
  return {
    apiPrefix: doctrinesUrl.replace(/doctrines\/?$/, ""),
    appName: root?.dataset.appName || "Doctrines",
    canManage: root?.dataset.canManage === "true",
    canViewCompliance: root?.dataset.canViewCompliance === "true",
    canManageRules: root?.dataset.canManageRules === "true",
    linkCharacterUrl: root?.dataset.linkCharacterUrl || "/doctrines/link-character/",
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
  const text = await response.text();
  let data: Record<string, unknown> = {};
  if (text) {
    try {
      data = JSON.parse(text) as Record<string, unknown>;
    } catch {
      throw new Error(`Unexpected response from server (HTTP ${response.status}).`);
    }
  }
  if (!response.ok) {
    throw new Error((data as { error?: string }).error || `Request failed (${response.status})`);
  }
  return data as T;
}

async function requestStream<T>(
  path: string,
  body: Record<string, unknown>,
  onLog: (message: string) => void,
): Promise<T> {
  const response = await fetch(`${config.apiPrefix}${path}`, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/x-ndjson, application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": config.csrfToken,
    },
    body: JSON.stringify({ ...body, stream: true }),
  });
  if (!response.ok) {
    const text = await response.text();
    let msg = `Request failed (${response.status})`;
    try {
      const parsed = JSON.parse(text) as { error?: string };
      if (parsed.error) msg = parsed.error;
    } catch {
      // non-JSON error
    }
    throw new Error(msg);
  }
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Streaming response is not supported by this browser.");
  }
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: T | undefined;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;
      const evt = JSON.parse(line) as { type: "log" | "result" | "error"; message?: string; data?: T; error?: string };
      if (evt.type === "log" && evt.message) {
        onLog(evt.message);
      } else if (evt.type === "error") {
        throw new Error(evt.error || "Scrape failed");
      } else if (evt.type === "result") {
        finalResult = evt.data;
      }
    }
  }
  if (finalResult === undefined) {
    throw new Error("Stream ended without a result.");
  }
  return finalResult;
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
  remoteScrapePreview: (
    payload: {
      base_url: string;
      sessionid: string;
      include_standalone_fits: boolean;
      include_categories: boolean;
      limit: number | null;
      offset: number;
      overwrite_existing: boolean;
    },
    onLog?: (message: string) => void,
  ) =>
    onLog
      ? requestStream<RemoteScrapePreview>("settings/remote-scrape/", { ...payload, mode: "preview" }, onLog)
      : request<RemoteScrapePreview>("settings/remote-scrape/", {
          method: "POST",
          body: JSON.stringify({ ...payload, mode: "preview" }),
        }),
  remoteScrapeImport: (
    payload: {
      base_url: string;
      sessionid: string;
      include_standalone_fits: boolean;
      include_categories: boolean;
      limit: number | null;
      offset: number;
      overwrite_existing: boolean;
    },
    onLog?: (message: string) => void,
  ) =>
    onLog
      ? requestStream<RemoteScrapeImportResult>("settings/remote-scrape/", { ...payload, mode: "import" }, onLog)
      : request<RemoteScrapeImportResult>("settings/remote-scrape/", {
          method: "POST",
          body: JSON.stringify({ ...payload, mode: "import" }),
        }),
  remoteScrapePurge: () => request<RemoteScrapePurgeResult>("settings/remote-scrape/purge/", { method: "POST" }),
  eligibilityStatus: () => request<EligibilityStatusResponse>("eligibility/status/"),
  eligibilitySync: () => request<EligibilityStatusResponse & { ok: boolean }>("eligibility/sync/", { method: "POST" }),
  fittingEligibility: (id: number) => request<FittingEligibilityResponse>(`fittings/${id}/eligibility/`),
  fittingSkillPlan: (id: number, target: "minimum" | "recommended" = "minimum", characterId?: number) =>
    request<{ skill_plan: string; target: string }>(
      `fittings/${id}/skill-plan/?target=${target}${characterId ? `&character_id=${characterId}` : ""}`,
    ),
  refreshFittingDogmaSkills: (id: number) =>
    request<{ count: number }>(`fittings/${id}/skills/`, { method: "POST", body: JSON.stringify({ refresh_dogma: true }) }),
  addFittingSkill: (
    id: number,
    payload: { skill_id: number; skill_name: string; required_level: number; recommended_level: number },
  ) => request(`fittings/${id}/skills/`, { method: "POST", body: JSON.stringify(payload) }),
  removeFittingSkill: (id: number, skill_id: number) =>
    request(`fittings/${id}/skills/`, { method: "DELETE", body: JSON.stringify({ skill_id }) }),
  complianceOverview: () => request<ComplianceOverviewResponse>("compliance/overview/"),
  searchSkills: (q: string, id?: number) =>
    request<{ skills: { id: number; name: string }[] }>(
      `skills/search/?q=${encodeURIComponent(q)}${id ? `&id=${id}` : ""}`,
    ).then((r) => r.skills),
  rules: () => request<{ rules: ComplianceRule[]; groups: { id: number; name: string }[] }>("rules/"),
  createRule: (payload: Partial<ComplianceRule>) =>
    request<ComplianceRule>("rules/", { method: "POST", body: JSON.stringify(payload) }),
  updateRule: (id: number, payload: Partial<ComplianceRule>) =>
    request<ComplianceRule>(`rules/${id}/`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteRule: (id: number) => request(`rules/${id}/`, { method: "DELETE" }),
  evaluateRules: () => request<{ ok: boolean; rules: number; evaluations: number }>("rules/evaluate/", { method: "POST" }),
  approvals: () => request<{ approvals: PendingApprovalItem[] }>("rules/approvals/"),
  decideApproval: (id: number, approve: boolean, note = "") =>
    request(`rules/approvals/${id}/decide/`, { method: "POST", body: JSON.stringify({ approve, note }) }),
  auditLogs: () => request<{ logs: AuditLogEntry[] }>("rules/audit/"),
  notificationSettings: () => request<NotificationSettings>("settings/notifications/"),
  saveNotificationSettings: (payload: Partial<NotificationSettings>) =>
    request<NotificationSettings>("settings/notifications/", { method: "PUT", body: JSON.stringify(payload) }),
  hangarCheck: (doctrineId?: number) =>
    request<{ ships: HangarShipMatch[] }>(`integrations/hangar-check/${doctrineId ? `?doctrine_id=${doctrineId}` : ""}`),
  pushIndustryOrder: (doctrineId: number) =>
    request<IndustryOrderResult>("integrations/industry-order/", {
      method: "POST",
      body: JSON.stringify({ doctrine_id: doctrineId }),
    }),
  srpCompare: (fittingId: number, killmail: Record<string, unknown>) =>
    request<SrpCompareResult>("integrations/srp-compare/", {
      method: "POST",
      body: JSON.stringify({ fitting_id: fittingId, killmail }),
    }),
};

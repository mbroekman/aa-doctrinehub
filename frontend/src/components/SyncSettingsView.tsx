import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type {
  RemoteScrapeImportResult,
  RemoteScrapePreview,
  RemoteScrapePurgeResult,
  SyncSettings,
} from "@/types";

export function SyncSettingsView() {
  const [settings, setSettings] = useState<SyncSettings | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [queued, setQueued] = useState(false);
  const [remoteUrl, setRemoteUrl] = useState("");
  const [remoteSessionId, setRemoteSessionId] = useState("");
  const [includeStandalone, setIncludeStandalone] = useState(true);
  const [includeCategories, setIncludeCategories] = useState(true);
  const [batchLimit, setBatchLimit] = useState("25");
  const [batchOffset, setBatchOffset] = useState("0");
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const [scrapeModeBusy, setScrapeModeBusy] = useState<"preview" | "import" | null>(null);
  const [scrapeError, setScrapeError] = useState("");
  const [scrapePreview, setScrapePreview] = useState<RemoteScrapePreview | null>(null);
  const [scrapeResult, setScrapeResult] = useState<RemoteScrapeImportResult | null>(null);
  const [confirmPurge, setConfirmPurge] = useState(false);
  const [purgeBusy, setPurgeBusy] = useState(false);
  const [purgeResult, setPurgeResult] = useState<RemoteScrapePurgeResult | null>(null);

  useEffect(() => {
    api.syncSettings().then(setSettings).catch((e: Error) => setError(e.message));
  }, []);

  const save = async (changes: Partial<SyncSettings>) => {
    setError("");
    try {
      setSettings(await api.saveSyncSettings(changes));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const runNow = async () => {
    setBusy(true);
    setError("");
    setQueued(false);
    try {
      await api.runFittingsSync();
      setQueued(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const runScrape = async (mode: "preview" | "import") => {
    setScrapeModeBusy(mode);
    setScrapeError("");
    setPurgeResult(null);
    if (mode === "preview") {
      setScrapeResult(null);
    }
    try {
      const parsedLimit = batchLimit.trim() ? Number(batchLimit.trim()) : null;
      const parsedOffset = Math.max(0, Number(batchOffset.trim() || "0") || 0);
      const payload = {
        base_url: remoteUrl,
        sessionid: remoteSessionId,
        include_standalone_fits: includeStandalone,
        include_categories: includeCategories,
        limit: parsedLimit && parsedLimit > 0 ? parsedLimit : null,
        offset: parsedOffset,
        overwrite_existing: overwriteExisting,
      };
      if (mode === "preview") {
        setScrapePreview(await api.remoteScrapePreview(payload));
      } else {
        const res = await api.remoteScrapeImport(payload);
        setScrapeResult(res);
        setScrapePreview(null);
        if (overwriteExisting && payload.limit && (res.doctrines.length > 0 || res.fittings_created + res.fittings_updated > 0)) {
          setBatchOffset(String(parsedOffset + payload.limit));
        }
      }
    } catch (e) {
      setScrapeError((e as Error).message);
    } finally {
      setScrapeModeBusy(null);
    }
  };

  const runPurge = async () => {
    setPurgeBusy(true);
    setScrapeError("");
    try {
      const res = await api.remoteScrapePurge();
      setPurgeResult(res);
      setScrapePreview(null);
      setScrapeResult(null);
      setConfirmPurge(false);
    } catch (e) {
      setScrapeError((e as Error).message);
    } finally {
      setPurgeBusy(false);
    }
  };

  if (!settings) return error ? <p className="text-sm text-destructive">{error}</p> : null;

  return (
    <div className="space-y-4">
      <Card>
      <CardHeader>
        <CardTitle>Sync from Fittings</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {!settings.fittings_app_installed && (
          <p className="text-muted-foreground">The Fittings app is not installed on this Auth, so there is nothing to sync.</p>
        )}
        <p className="text-muted-foreground">
          Copies doctrines, fittings and categories from the Fittings app. Synced items are labelled "Fittings" and are
          read-only here.
        </p>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={settings.fittings_sync_enabled}
            onChange={(e) => void save({ fittings_sync_enabled: e.target.checked })}
          />
          Sync automatically
        </label>
        <label className="flex items-center gap-2">
          Every
          <Input
            type="number"
            min={1}
            max={90}
            className="w-20"
            value={settings.fittings_sync_interval_days}
            onChange={(e) => setSettings({ ...settings, fittings_sync_interval_days: Number(e.target.value) })}
            onBlur={() => void save({ fittings_sync_interval_days: settings.fittings_sync_interval_days })}
          />
          days
        </label>
        <div className="flex items-center gap-3">
          <Button size="sm" onClick={runNow} disabled={busy || !settings.fittings_app_installed}>
            Sync now
          </Button>
          <span className="text-muted-foreground">
            {settings.fittings_last_sync_at
              ? `Last sync ${new Date(settings.fittings_last_sync_at).toLocaleString()}. ${settings.fittings_last_sync_summary}`
              : "Never synced."}
          </span>
        </div>
        {queued && (
          <p className="text-muted-foreground">
            Sync queued - this runs in the background and may take a moment. Reopen this page to see the result.
          </p>
        )}
        {error && <p className="text-destructive">{error}</p>}
      </CardContent>
    </Card>

      <Card>
        <CardHeader>
          <CardTitle>Import from External Auth</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p className="text-muted-foreground">
            Scrapes doctrines, fittings and categories from another Alliance Auth instance using a one-time{" "}
            <code>sessionid</code> cookie. The cookie is never stored. Imported items are labelled "External Auth" and
            remain read-only here.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1">
              <span className="block text-xs font-medium text-muted-foreground">External Auth URL</span>
              <Input
                type="url"
                placeholder="https://zero.the-initiative.rocks"
                value={remoteUrl}
                onChange={(e) => setRemoteUrl(e.target.value)}
              />
            </label>
            <label className="space-y-1">
              <span className="block text-xs font-medium text-muted-foreground">sessionid cookie (DevTools)</span>
              <Input
                type="password"
                placeholder="Paste sessionid cookie value"
                value={remoteSessionId}
                onChange={(e) => setRemoteSessionId(e.target.value)}
              />
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">Max items per batch (blank = all)</span>
              <Input
                type="number"
                min={1}
                placeholder="All"
                className="w-24"
                value={batchLimit}
                onChange={(e) => setBatchLimit(e.target.value)}
              />
            </label>
            <label className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">Start at # (offset)</span>
              <Input
                type="number"
                min={0}
                className="w-24"
                value={batchOffset}
                onChange={(e) => setBatchOffset(e.target.value)}
              />
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={overwriteExisting}
                onChange={(e) => {
                  const checked = e.target.checked;
                  setOverwriteExisting(checked);
                  if (!checked) setBatchOffset("0");
                }}
              />
              Overwrite existing
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeStandalone}
                onChange={(e) => setIncludeStandalone(e.target.checked)}
              />
              Include standalone fits
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeCategories}
                onChange={(e) => setIncludeCategories(e.target.checked)}
              />
              Include categories
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={scrapeModeBusy !== null || !remoteUrl.trim() || !remoteSessionId.trim()}
              onClick={() => void runScrape("preview")}
            >
              {scrapeModeBusy === "preview" ? "Previewing..." : "Preview"}
            </Button>
            <Button
              size="sm"
              disabled={scrapeModeBusy !== null || purgeBusy || !remoteUrl.trim() || !remoteSessionId.trim()}
              onClick={() => void runScrape("import")}
            >
              {scrapeModeBusy === "import" ? "Importing..." : "Import now"}
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={scrapeModeBusy !== null || purgeBusy}
              onClick={() => setConfirmPurge(true)}
            >
              Delete imported items
            </Button>
            {scrapeModeBusy === "preview" && (
              <span className="text-xs text-muted-foreground">Reading index pages from external Auth...</span>
            )}
            {scrapeModeBusy === "import" && (
              <span className="text-xs text-muted-foreground">
                Scraping and importing batch (this may take a moment)...
              </span>
            )}
          </div>
          {confirmPurge && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs">
                Delete all imported External Auth doctrines, fittings, and categories? Local Doctrine Hub items will not
                be affected.
              </span>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={purgeBusy}
                  onClick={() => setConfirmPurge(false)}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={purgeBusy}
                  onClick={() => void runPurge()}
                >
                  {purgeBusy ? "Deleting..." : "Confirm delete"}
                </Button>
              </div>
            </div>
          )}
          {purgeResult && (
            <div className="rounded-md border p-3 text-xs">
              Deleted {purgeResult.doctrines_deleted} doctrines, {purgeResult.fittings_deleted} fittings, and{" "}
              {purgeResult.categories_deleted} categories from External Auth.
            </div>
          )}
          {scrapePreview && (
            <div className="rounded-md border p-3 space-y-2">
              <div className="font-medium">Preview summary</div>
              <div className="grid gap-2 sm:grid-cols-3 text-xs">
                <div className="rounded border p-2">
                  <div className="font-medium">Doctrines</div>
                  <div className="text-muted-foreground">
                    Source total: {scrapePreview.doctrines_total} (already imported:{" "}
                    {scrapePreview.doctrines_already_imported})
                  </div>
                  <div>
                    Next batch: {scrapePreview.doctrines_count} ({scrapePreview.doctrines_new} new)
                  </div>
                </div>
                <div className="rounded border p-2">
                  <div className="font-medium">Fittings</div>
                  <div className="text-muted-foreground">
                    Source total: {scrapePreview.fittings_total} (already imported:{" "}
                    {scrapePreview.fittings_already_imported})
                  </div>
                  <div>
                    Next batch: {scrapePreview.fittings_count} ({scrapePreview.fittings_new} new)
                  </div>
                </div>
                <div className="rounded border p-2">
                  <div className="font-medium">Categories</div>
                  <div className="text-muted-foreground">
                    Source total: {scrapePreview.categories_total} (already imported:{" "}
                    {scrapePreview.categories_already_imported})
                  </div>
                  <div>
                    Next batch: {scrapePreview.categories_count} ({scrapePreview.categories_new} new)
                  </div>
                </div>
              </div>
              {scrapePreview.doctrines.length > 0 && (
                <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-0.5 max-h-40 overflow-y-auto">
                  {scrapePreview.doctrines.map((d) => (
                    <li key={d.external_id}>
                      {d.name}
                      {d.fittings_count !== null ? ` (${d.fittings_count} fits)` : ""}
                      {d.is_new ? " — new" : ""}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {scrapeResult && (
            <div className="rounded-md border p-3 space-y-2">
              <div className="font-medium">Import summary</div>
              <div className="grid gap-2 sm:grid-cols-3 text-xs">
                <div className="rounded border p-2">
                  <div className="font-medium">Doctrines</div>
                  <div>
                    +{scrapeResult.doctrines_created} new, {scrapeResult.doctrines_updated} updated
                    {scrapeResult.doctrines_archived > 0 ? `, ${scrapeResult.doctrines_archived} archived` : ""}
                  </div>
                  <div className="text-muted-foreground">
                    Total stored: {scrapeResult.total_doctrines_stored}
                  </div>
                </div>
                <div className="rounded border p-2">
                  <div className="font-medium">Fittings</div>
                  <div>
                    +{scrapeResult.fittings_created} new, {scrapeResult.fittings_updated} updated
                    {scrapeResult.fittings_removed > 0 ? `, ${scrapeResult.fittings_removed} removed` : ""}
                  </div>
                  <div className="text-muted-foreground">
                    Total stored: {scrapeResult.total_fittings_stored}
                  </div>
                </div>
                <div className="rounded border p-2">
                  <div className="font-medium">Categories</div>
                  <div>{scrapeResult.categories_synced} synced</div>
                  <div className="text-muted-foreground">
                    Total stored: {scrapeResult.total_categories_stored}
                  </div>
                </div>
              </div>
              {scrapeResult.doctrines.length > 0 && (
                <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-0.5 max-h-40 overflow-y-auto">
                  {scrapeResult.doctrines.map((d) => (
                    <li key={d.external_id}>
                      {d.name} ({d.fittings_count} fits)
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {scrapeError && <p className="text-destructive">{scrapeError}</p>}
        </CardContent>
      </Card>
    </div>
  );
}

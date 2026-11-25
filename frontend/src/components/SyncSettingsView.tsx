import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { RemoteScrapeImportResult, RemoteScrapePreview, SyncSettings } from "@/types";

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
  const [skipExisting, setSkipExisting] = useState(true);
  const [scrapeBusy, setScrapeBusy] = useState(false);
  const [scrapeError, setScrapeError] = useState("");
  const [scrapePreview, setScrapePreview] = useState<RemoteScrapePreview | null>(null);
  const [scrapeResult, setScrapeResult] = useState<RemoteScrapeImportResult | null>(null);

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
    setScrapeBusy(true);
    setScrapeError("");
    if (mode === "preview") {
      setScrapeResult(null);
    }
    try {
      const parsedLimit = batchLimit.trim() ? Number(batchLimit.trim()) : null;
      const payload = {
        base_url: remoteUrl,
        sessionid: remoteSessionId,
        include_standalone_fits: includeStandalone,
        include_categories: includeCategories,
        limit: parsedLimit && parsedLimit > 0 ? parsedLimit : null,
        skip_existing: skipExisting,
      };
      if (mode === "preview") {
        setScrapePreview(await api.remoteScrapePreview(payload));
      } else {
        setScrapeResult(await api.remoteScrapeImport(payload));
      }
    } catch (e) {
      setScrapeError((e as Error).message);
    } finally {
      setScrapeBusy(false);
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
              <input
                type="checkbox"
                checked={skipExisting}
                onChange={(e) => setSkipExisting(e.target.checked)}
              />
              Skip already imported
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
              disabled={scrapeBusy || !remoteUrl.trim() || !remoteSessionId.trim()}
              onClick={() => void runScrape("preview")}
            >
              Preview
            </Button>
            <Button
              size="sm"
              disabled={scrapeBusy || !remoteUrl.trim() || !remoteSessionId.trim()}
              onClick={() => void runScrape("import")}
            >
              Import now
            </Button>
          </div>
          {scrapePreview && (
            <div className="rounded-md border p-3 space-y-2">
              <div className="font-medium">
                Preview: {scrapePreview.doctrines_count} doctrines ({scrapePreview.doctrines_new} new),{" "}
                {scrapePreview.fittings_count} fittings ({scrapePreview.fittings_new} new),{" "}
                {scrapePreview.categories_count} categories ({scrapePreview.categories_new} new).
              </div>
              {scrapePreview.doctrines.length > 0 && (
                <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-0.5 max-h-40 overflow-y-auto">
                  {scrapePreview.doctrines.map((d) => (
                    <li key={d.external_id}>
                      {d.name} ({d.fittings_count} fits){d.is_new ? " — new" : ""}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {scrapeResult && (
            <p className="text-muted-foreground">Import complete: {scrapeResult.summary}</p>
          )}
          {scrapeError && <p className="text-destructive">{scrapeError}</p>}
        </CardContent>
      </Card>
    </div>
  );
}

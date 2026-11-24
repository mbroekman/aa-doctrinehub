import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { SyncSettings } from "@/types";

export function SyncSettingsView({ onSynced }: { onSynced: () => void }) {
  const [settings, setSettings] = useState<SyncSettings | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
    try {
      setSettings(await api.runFittingsSync());
      onSynced();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!settings) return error ? <p className="text-sm text-destructive">{error}</p> : null;

  return (
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
        {error && <p className="text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}

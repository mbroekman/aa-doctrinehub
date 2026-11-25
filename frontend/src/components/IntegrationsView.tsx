import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, Send, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Doctrine, FittingSummary, HangarShipMatch, IndustryOrderResult, SrpCompareResult } from "@/types";

export function IntegrationsView({
  doctrines,
  fittings,
  canManage,
}: {
  doctrines: Doctrine[];
  fittings: FittingSummary[];
  canManage: boolean;
}) {
  const [ships, setShips] = useState<HangarShipMatch[]>([]);
  const [loadingHangars, setLoadingHangars] = useState(false);
  const [hangarDoctrineId, setHangarDoctrineId] = useState<number>(0);
  const [hangarCharacter, setHangarCharacter] = useState<string>("all");
  const [selectedDoctrineId, setSelectedDoctrineId] = useState<number>(doctrines[0]?.id ?? 0);
  const [industryResult, setIndustryResult] = useState<IndustryOrderResult | null>(null);
  const [srpFittingId, setSrpFittingId] = useState<number>(fittings[0]?.id ?? 0);
  const [killmailJson, setKillmailJson] = useState("");
  const [srpResult, setSrpResult] = useState<SrpCompareResult | null>(null);
  const [error, setError] = useState("");

  const loadHangars = useCallback(() => {
    setLoadingHangars(true);
    setError("");
    api
      .hangarCheck(hangarDoctrineId || undefined)
      .then((res) => setShips(res.ships))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoadingHangars(false));
  }, [hangarDoctrineId]);

  useEffect(loadHangars, [loadHangars]);

  const characterNames = useMemo(
    () => Array.from(new Set(ships.map((s) => s.character_name))).sort((a, b) => a.localeCompare(b)),
    [ships],
  );

  const groupedByCharacter = useMemo(() => {
    const groups = new Map<string, HangarShipMatch[]>();
    for (const ship of ships) {
      if (hangarCharacter !== "all" && ship.character_name !== hangarCharacter) continue;
      const list = groups.get(ship.character_name) ?? [];
      list.push(ship);
      groups.set(ship.character_name, list);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [ships, hangarCharacter]);

  const handleIndustryPush = async () => {
    if (!selectedDoctrineId) return;
    setError("");
    try {
      const res = await api.pushIndustryOrder(selectedDoctrineId);
      setIndustryResult(res);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleSrpCompare = async () => {
    if (!srpFittingId || !killmailJson.trim()) return;
    setError("");
    try {
      const parsed = JSON.parse(killmailJson) as Record<string, unknown>;
      const res = await api.srpCompare(srpFittingId, parsed);
      setSrpResult(res);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardHeader className="flex flex-wrap flex-row items-center justify-between gap-2">
          <CardTitle className="text-base">Hangar Check (Fitted Doctrine Ships)</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Filter hangar check by doctrine"
              value={hangarDoctrineId}
              onChange={(e) => setHangarDoctrineId(Number(e.target.value))}
              className="h-8 rounded-md border border-input bg-background px-2.5 text-xs"
            >
              <option value={0}>All doctrines</option>
              {doctrines.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter hangar check by character"
              value={hangarCharacter}
              onChange={(e) => setHangarCharacter(e.target.value)}
              className="h-8 rounded-md border border-input bg-background px-2.5 text-xs"
            >
              <option value="all">All characters ({characterNames.length})</option>
              {characterNames.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <Button size="sm" variant="outline" onClick={loadHangars} disabled={loadingHangars}>
              <RefreshCw className={`mr-1 h-3.5 w-3.5 ${loadingHangars ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {groupedByCharacter.length ? (
            groupedByCharacter.map(([charName, charShips]) => (
              <div key={charName} className="rounded-md border border-border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-semibold">{charName}</span>
                  <Badge variant="secondary">{charShips.length} ship(s)</Badge>
                </div>
                <ul className="space-y-1.5 text-sm">
                  {charShips.map((s) => (
                    <li
                      key={`${s.character_id}-${s.item_id}-${s.fitting_id}`}
                      className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-1.5 first:border-t-0 first:pt-0"
                    >
                      <span>
                        {s.ship_type_name} ({s.fitting_name}) ·{" "}
                        <span className="text-xs text-muted-foreground">Location {s.location_id}</span>
                      </span>
                      <Badge variant={s.match_status === "full" ? "default" : "secondary"}>
                        {s.match_status} ({s.match_pct}%)
                      </Badge>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">
              No matching doctrine ships found in synced character assets.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {canManage && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Push Shortages to aa-industry</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <select
                  value={selectedDoctrineId}
                  onChange={(e) => setSelectedDoctrineId(Number(e.target.value))}
                  className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm"
                >
                  {doctrines.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
                <Button size="sm" onClick={handleIndustryPush} disabled={!selectedDoctrineId}>
                  <Send className="mr-1 h-3.5 w-3.5" />
                  Push Order
                </Button>
              </div>
              {industryResult && (
                <div className="space-y-1 text-xs">
                  <p className="font-medium">{industryResult.message}</p>
                  {industryResult.shortages.map((s) => (
                    <div key={s.fitting_id} className="text-muted-foreground">
                      {s.ship_type_name} ({s.fitting_name}): {s.owned_count}/{s.target_count} (shortage {s.shortage})
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">SRP Killmail vs. Doctrine Fit</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <select
              value={srpFittingId}
              onChange={(e) => setSrpFittingId(Number(e.target.value))}
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
            >
              {fittings.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.ship_type_name} — {f.name}
                </option>
              ))}
            </select>
            <textarea
              rows={4}
              value={killmailJson}
              onChange={(e) => setKillmailJson(e.target.value)}
              placeholder='Paste ESI killmail JSON ({"victim": {"ship_type_id": ..., "items": [...]}})'
              className="w-full rounded-md border border-input bg-background p-2 font-mono text-xs"
            />
            <Button size="sm" onClick={handleSrpCompare} disabled={!srpFittingId || !killmailJson.trim()}>
              <ShieldCheck className="mr-1 h-3.5 w-3.5" />
              Compare for SRP
            </Button>
            {srpResult && (
              <div className="space-y-1 text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant={srpResult.hull_match ? "default" : "destructive"}>
                    {srpResult.hull_match ? "Hull matches" : "Wrong hull"}
                  </Badge>
                  <span className="font-medium">{srpResult.compliance_pct}% module match</span>
                </div>
                {srpResult.missing.length > 0 && (
                  <p className="text-destructive">
                    Missing: {srpResult.missing.map((m) => `${m.quantity}x ${m.type_name}`).join(", ")}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

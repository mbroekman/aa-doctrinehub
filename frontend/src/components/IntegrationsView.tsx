import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, ChevronRight, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Doctrine, FittingSummary, HangarShipMatch, IndustryOrderResult, SrpCompareResult } from "@/types";

type HangarSortKey = "ship" | "doctrine" | "location" | "match";

function matchBadgeClass(pct: number): string {
  if (pct >= 100) return "bg-emerald-600 text-white";
  if (pct >= 80) return "bg-amber-500 text-black";
  if (pct >= 50) return "bg-orange-600 text-white";
  return "bg-destructive text-destructive-foreground";
}

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
  const [hangarMatchFilter, setHangarMatchFilter] = useState<"all" | "full" | "incomplete">("all");
  const [expandedChars, setExpandedChars] = useState<Record<string, boolean>>({});
  const [sortKey, setSortKey] = useState<HangarSortKey>("ship");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
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

  const toggleSort = (key: HangarSortKey) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "match" ? "desc" : "asc");
    }
  };

  const renderSortIcon = (key: HangarSortKey) => {
    if (sortKey !== key) return <ArrowUpDown className="ml-1 inline h-3 w-3 opacity-50" />;
    return sortDir === "asc" ? (
      <ArrowUp className="ml-1 inline h-3 w-3" />
    ) : (
      <ArrowDown className="ml-1 inline h-3 w-3" />
    );
  };

  const characterNames = useMemo(
    () => Array.from(new Set(ships.map((s) => s.character_name))).sort((a, b) => a.localeCompare(b)),
    [ships],
  );

  const groupedByCharacter = useMemo(() => {
    const groups = new Map<string, HangarShipMatch[]>();
    for (const ship of ships) {
      if (hangarCharacter !== "all" && ship.character_name !== hangarCharacter) continue;
      if (hangarMatchFilter === "full" && ship.match_pct < 100) continue;
      if (hangarMatchFilter === "incomplete" && ship.match_pct === 100) continue;
      const list = groups.get(ship.character_name) ?? [];
      list.push(ship);
      groups.set(ship.character_name, list);
    }
    const factor = sortDir === "asc" ? 1 : -1;
    for (const list of groups.values()) {
      list.sort((a, b) => {
        if (sortKey === "match") return (a.match_pct - b.match_pct) * factor;
        if (sortKey === "location") return a.location_name.localeCompare(b.location_name) * factor;
        if (sortKey === "doctrine") {
          return (a.doctrine_names[0] || "").localeCompare(b.doctrine_names[0] || "") * factor;
        }
        return `${a.ship_type_name} ${a.fitting_name}`.localeCompare(`${b.ship_type_name} ${b.fitting_name}`) * factor;
      });
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [ships, hangarCharacter, hangarMatchFilter, sortKey, sortDir]);

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
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
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
            <select
              aria-label="Filter hangar check by match status"
              value={hangarMatchFilter}
              onChange={(e) => setHangarMatchFilter(e.target.value as "all" | "full" | "incomplete")}
              className="h-8 rounded-md border border-input bg-background px-2.5 text-xs"
            >
              <option value="all">All (100% &amp; partial)</option>
              <option value="full">Only 100% (Full)</option>
              <option value="incomplete">Not 100% (Incomplete)</option>
            </select>
            <Button size="sm" variant="outline" onClick={loadHangars} disabled={loadingHangars}>
              <RefreshCw className={`mr-1 h-3.5 w-3.5 ${loadingHangars ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {loadingHangars ? (
            <div className="flex items-center justify-center gap-3 rounded-md border border-border bg-muted/30 p-8 text-sm text-muted-foreground">
              <RefreshCw className="h-5 w-5 animate-spin" />
              <span>Loading hangar ships and resolving station/structure names, please wait...</span>
            </div>
          ) : groupedByCharacter.length ? (
            groupedByCharacter.map(([charName, charShips]) => {
              const isOpen = Boolean(expandedChars[charName]);
              const fullCount = charShips.filter((s) => s.match_pct === 100).length;
              return (
                <div key={charName} className="rounded-md border border-border p-3">
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedChars((prev) => ({ ...prev, [charName]: !prev[charName] }))
                    }
                    className="flex w-full items-center justify-between text-left hover:text-foreground"
                  >
                    <span className="flex items-center gap-2 text-sm font-semibold">
                      {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      {charName}
                    </span>
                    <div className="flex items-center gap-1.5">
                      {fullCount > 0 && (
                        <Badge className="bg-emerald-600 text-white">{fullCount} full</Badge>
                      )}
                      <Badge variant="secondary">{charShips.length} ship(s)</Badge>
                    </div>
                  </button>
                  {isOpen && (
                    <div className="mt-3 overflow-x-auto border-t border-border/50 pt-2">
                      <table className="w-full text-left text-sm">
                        <thead>
                          <tr className="border-b border-border text-xs uppercase text-muted-foreground">
                            <th className="py-1.5 pr-3">
                              <button type="button" onClick={() => toggleSort("ship")} className="font-semibold hover:text-foreground">
                                Ship {renderSortIcon("ship")}
                              </button>
                            </th>
                            <th className="py-1.5 pr-3">
                              <button type="button" onClick={() => toggleSort("doctrine")} className="font-semibold hover:text-foreground">
                                Doctrine {renderSortIcon("doctrine")}
                              </button>
                            </th>
                            <th className="py-1.5 pr-3">
                              <button type="button" onClick={() => toggleSort("location")} className="font-semibold hover:text-foreground">
                                Location {renderSortIcon("location")}
                              </button>
                            </th>
                            <th className="py-1.5 text-right">
                              <button type="button" onClick={() => toggleSort("match")} className="font-semibold hover:text-foreground">
                                100% / Fit {renderSortIcon("match")}
                              </button>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {charShips.map((s) => (
                            <tr key={`${s.character_id}-${s.item_id}-${s.fitting_id}`} className="border-b border-border/50 last:border-b-0">
                              <td className="py-1.5 pr-3">
                                <span className="font-medium">{s.ship_type_name}</span>{" "}
                                <span className="text-muted-foreground">({s.fitting_name})</span>
                              </td>
                              <td className="py-1.5 pr-3 text-xs text-muted-foreground">
                                {s.doctrine_names.length ? s.doctrine_names.join(", ") : "—"}
                              </td>
                              <td className="py-1.5 pr-3 text-xs text-muted-foreground">{s.location_name}</td>
                              <td className="py-1.5 text-right">
                                <Badge className={matchBadgeClass(s.match_pct)}>
                                  {s.match_pct === 100 ? "100% Full" : `${s.match_pct}% (${s.match_status})`}
                                </Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })
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
                  <Badge className={matchBadgeClass(srpResult.compliance_pct)}>
                    {srpResult.compliance_pct}% module match
                  </Badge>
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

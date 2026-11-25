import { useCallback, useEffect, useMemo, useState } from "react";
import { Link2, Plus, RefreshCw, Search, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ComplianceView } from "@/components/ComplianceView";
import { FittingDialog } from "@/components/FittingDialog";
import { ImportDialog } from "@/components/ImportDialog";
import { IntegrationsView } from "@/components/IntegrationsView";
import { RulesView } from "@/components/RulesView";
import { ShipIcon } from "@/components/ShipIcon";
import { SourceBadge } from "@/components/SourceBadge";
import { SyncSettingsView } from "@/components/SyncSettingsView";
import { api, getSpaConfig } from "@/lib/api";
import type { Doctrine, EligibilityStatusResponse, FittingSummary } from "@/types";

const STATUS_LABEL: Record<Doctrine["status"], string> = {
  draft: "Draft",
  active: "Active",
  phasing_out: "Phasing out",
  archived: "Archived",
};

function DoctrineCard({ doctrine, onOpenFitting }: { doctrine: Doctrine; onOpenFitting: (id: number) => void }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          {doctrine.name}
          {doctrine.status !== "active" && <Badge variant="secondary">{STATUS_LABEL[doctrine.status]}</Badge>}
          <SourceBadge source={doctrine.source} />
          {doctrine.categories.map((c) => (
            <Badge key={c.id} variant="outline" style={{ borderColor: c.color }}>
              {c.name}
            </Badge>
          ))}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {doctrine.description && <p className="mb-3 text-sm text-muted-foreground">{doctrine.description}</p>}
        <ul className="space-y-1">
          {doctrine.fittings.map((f) => (
            <li key={f.id}>
              <button
                type="button"
                onClick={() => onOpenFitting(f.id)}
                className="flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent"
              >
                <ShipIcon typeId={f.ship_type_id} />
                <span className="font-medium">{f.ship_type_name}</span>
                <span className="text-muted-foreground">{f.name}</span>
                {f.role && <Badge variant="secondary">{f.role}</Badge>}
                {!f.is_required && <Badge variant="outline">optional</Badge>}
                {f.target_count ? <span className="ml-auto text-xs text-muted-foreground">x{f.target_count}</span> : null}
              </button>
            </li>
          ))}
          {!doctrine.fittings.length && <li className="text-sm text-muted-foreground">No fittings yet.</li>}
        </ul>
      </CardContent>
    </Card>
  );
}

function FittingList({ fittings, onOpenFitting }: { fittings: FittingSummary[]; onOpenFitting: (id: number) => void }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {fittings.map((f) => (
        <li key={f.id}>
          <button
            type="button"
            onClick={() => onOpenFitting(f.id)}
            className="flex w-full items-center gap-3 rounded-md border border-border bg-card px-3 py-2 text-left text-sm hover:bg-accent"
          >
            <ShipIcon typeId={f.ship_type_id} />
            <span className="min-w-0 flex-1">
              <span className="block font-medium">{f.ship_type_name}</span>
              <span className="block truncate text-muted-foreground">{f.name}</span>
            </span>
            <SourceBadge source={f.source} />
          </button>
        </li>
      ))}
    </ul>
  );
}

export function App() {
  const config = useMemo(getSpaConfig, []);
  const [doctrines, setDoctrines] = useState<Doctrine[]>([]);
  const [fittings, setFittings] = useState<FittingSummary[]>([]);
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [openFitting, setOpenFitting] = useState<number | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [eligStatus, setEligStatus] = useState<EligibilityStatusResponse | null>(null);
  const [syncingEsi, setSyncingEsi] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    Promise.all([api.doctrines(), api.fittings()])
      .then(([d, f]) => {
        setDoctrines(d);
        setFittings(f);
      })
      .catch((e: Error) => setError(e.message));
    api.eligibilityStatus().then(setEligStatus).catch(() => undefined);
  }, []);

  const handleSyncEsi = () => {
    setSyncingEsi(true);
    api
      .eligibilitySync()
      .then((res) => setEligStatus({ all_linked: res.characters.every((c) => c.has_valid_token), characters: res.characters }))
      .catch((e: Error) => setError(e.message))
      .finally(() => setSyncingEsi(false));
  };

  useEffect(load, [load]);

  const categoryOptions = useMemo(() => {
    const names = new Set<string>();
    for (const d of doctrines) {
      for (const c of d.categories) names.add(c.name);
    }
    for (const f of fittings) {
      for (const c of f.categories) names.add(c.name);
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b));
  }, [doctrines, fittings]);

  const sourceOptions = useMemo(() => {
    const sources = new Set<string>();
    for (const d of doctrines) sources.add(d.source);
    for (const f of fittings) sources.add(f.source);
    return Array.from(sources);
  }, [doctrines, fittings]);

  const needle = query.trim().toLowerCase();
  const shownDoctrines = doctrines.filter((d) => {
    if (sourceFilter !== "all" && d.source !== sourceFilter) return false;
    if (
      categoryFilter !== "all" &&
      !d.categories.some((c) => c.name === categoryFilter) &&
      !d.fittings.some((f) => f.categories.some((c) => c.name === categoryFilter))
    ) {
      return false;
    }
    if (!needle) return true;
    return (
      d.name.toLowerCase().includes(needle) ||
      d.description.toLowerCase().includes(needle) ||
      d.categories.some((c) => c.name.toLowerCase().includes(needle)) ||
      d.fittings.some((f) =>
        `${f.ship_type_name} ${f.name} ${f.role} ${f.categories.map((c) => c.name).join(" ")}`
          .toLowerCase()
          .includes(needle),
      )
    );
  });
  const shownFittings = fittings.filter((f) => {
    if (sourceFilter !== "all" && f.source !== sourceFilter) return false;
    if (categoryFilter !== "all" && !f.categories.some((c) => c.name === categoryFilter)) return false;
    if (!needle) return true;
    return `${f.ship_type_name} ${f.name} ${f.categories.map((c) => c.name).join(" ")}`
      .toLowerCase()
      .includes(needle);
  });

  const hasActiveFilter = Boolean(needle) || categoryFilter !== "all" || sourceFilter !== "all";

  return (
    <div className="space-y-4 p-1">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search doctrines, ships, fits, categories..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-8 pr-8"
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => setQuery("")}
              className="absolute right-2 top-2.5 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        {categoryOptions.length > 0 && (
          <select
            aria-label="Filter by category"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="all">All categories</option>
            {categoryOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        )}
        {sourceOptions.length > 1 && (
          <select
            aria-label="Filter by source"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="all">All sources</option>
            {sourceOptions.includes("local") && <option value="local">Doctrine Hub</option>}
            {sourceOptions.includes("fittings") && <option value="fittings">Fittings</option>}
            {sourceOptions.includes("remote_auth") && <option value="remote_auth">External Auth</option>}
          </select>
        )}
        {hasActiveFilter && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setQuery("");
              setCategoryFilter("all");
              setSourceFilter("all");
            }}
          >
            Reset
          </Button>
        )}
        {config.canManage && (
          <Button size="sm" className="ml-auto" onClick={() => setImportOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Import EFT
          </Button>
        )}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {eligStatus && !eligStatus.all_linked && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
          <span>
            Some characters are missing required ESI scopes for skill &amp; hangar checks.
          </span>
          <Button size="sm" variant="default" asChild>
            <a href={config.linkCharacterUrl}>
              <Link2 className="mr-1 h-3.5 w-3.5" />
              Link Character
            </a>
          </Button>
        </div>
      )}
      <Tabs defaultValue="doctrines">
        <TabsList>
          <TabsTrigger value="doctrines">
            Doctrines ({hasActiveFilter ? `${shownDoctrines.length}/${doctrines.length}` : doctrines.length})
          </TabsTrigger>
          <TabsTrigger value="fittings">
            Fittings ({hasActiveFilter ? `${shownFittings.length}/${fittings.length}` : fittings.length})
          </TabsTrigger>
          <TabsTrigger value="characters">
            ESI Characters ({eligStatus?.characters.length ?? 0})
          </TabsTrigger>
          {config.canViewCompliance && <TabsTrigger value="compliance">Compliance</TabsTrigger>}
          {config.canManageRules && <TabsTrigger value="rules">Rules &amp; Groups</TabsTrigger>}
          <TabsTrigger value="integrations">Hangars &amp; SRP</TabsTrigger>
          {config.canManage && <TabsTrigger value="settings">Settings</TabsTrigger>}
        </TabsList>
        <TabsContent value="doctrines" className="grid gap-4 lg:grid-cols-2">
          {shownDoctrines.map((d) => (
            <DoctrineCard key={d.id} doctrine={d} onOpenFitting={setOpenFitting} />
          ))}
          {!shownDoctrines.length && <p className="text-sm text-muted-foreground">No doctrines to show.</p>}
        </TabsContent>
        <TabsContent value="fittings">
          {shownFittings.length > 0 ? (
            <FittingList fittings={shownFittings} onOpenFitting={setOpenFitting} />
          ) : (
            <p className="text-sm text-muted-foreground">No fittings to show.</p>
          )}
        </TabsContent>
        <TabsContent value="characters">
          <Card>
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base">ESI Characters &amp; Skill Snapshots</CardTitle>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="default" asChild>
                  <a href={config.linkCharacterUrl}>
                    <Link2 className="mr-1 h-3.5 w-3.5" />
                    Link Character
                  </a>
                </Button>
                <Button size="sm" variant="outline" onClick={handleSyncEsi} disabled={syncingEsi}>
                  <RefreshCw className={`mr-1 h-3.5 w-3.5 ${syncingEsi ? "animate-spin" : ""}`} />
                  Sync All Now
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {eligStatus?.characters.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs uppercase text-muted-foreground">
                        <th className="py-2 pr-3">Character</th>
                        <th className="py-2 pr-3">Scopes</th>
                        <th className="py-2 pr-3">Snapshot Status</th>
                        <th className="py-2 pr-3 text-right">Total SP</th>
                        <th className="py-2 text-right">Last Synced</th>
                      </tr>
                    </thead>
                    <tbody>
                      {eligStatus.characters.map((c) => (
                        <tr key={c.character_id} className="border-b border-border/50 last:border-b-0">
                          <td className="py-2 pr-3 font-medium">{c.character_name}</td>
                          <td className="py-2 pr-3">
                            <Badge variant={c.has_valid_token ? "default" : "destructive"}>
                              {c.has_valid_token ? "Valid" : "Missing scopes"}
                            </Badge>
                          </td>
                          <td className="py-2 pr-3">
                            <Badge variant={c.sync_status === "ok" ? "secondary" : c.sync_status === "error" ? "destructive" : "outline"}>
                              {c.sync_status}
                            </Badge>
                            {c.last_error && (
                              <span className="ml-2 text-xs text-destructive">{c.last_error}</span>
                            )}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono text-xs">
                            {c.total_sp ? c.total_sp.toLocaleString() : "—"}
                          </td>
                          <td className="py-2 text-right text-xs text-muted-foreground">
                            {c.last_synced_at ? new Date(c.last_synced_at).toLocaleString() : "Never"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No characters linked yet. Click <strong>Link Character</strong> to authorize ESI scopes.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        {config.canViewCompliance && (
          <TabsContent value="compliance">
            <ComplianceView />
          </TabsContent>
        )}
        {config.canManageRules && (
          <TabsContent value="rules">
            <RulesView doctrines={doctrines} fittings={fittings} />
          </TabsContent>
        )}
        <TabsContent value="integrations">
          <IntegrationsView doctrines={doctrines} fittings={fittings} canManage={config.canManage} />
        </TabsContent>
        {config.canManage && (
          <TabsContent value="settings">
            <SyncSettingsView />
          </TabsContent>
        )}
      </Tabs>
      <FittingDialog fittingId={openFitting} onClose={() => setOpenFitting(null)} />
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} onImported={load} />
    </div>
  );
}

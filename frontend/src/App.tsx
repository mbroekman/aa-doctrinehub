import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { FittingDialog } from "@/components/FittingDialog";
import { ImportDialog } from "@/components/ImportDialog";
import { ShipIcon } from "@/components/ShipIcon";
import { SourceBadge } from "@/components/SourceBadge";
import { SyncSettingsView } from "@/components/SyncSettingsView";
import { api, getSpaConfig } from "@/lib/api";
import type { Doctrine, FittingSummary } from "@/types";

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
  const [openFitting, setOpenFitting] = useState<number | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    Promise.all([api.doctrines(), api.fittings()])
      .then(([d, f]) => {
        setDoctrines(d);
        setFittings(f);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  const needle = query.trim().toLowerCase();
  const shownDoctrines = doctrines.filter(
    (d) =>
      !needle ||
      d.name.toLowerCase().includes(needle) ||
      d.fittings.some((f) => `${f.ship_type_name} ${f.name}`.toLowerCase().includes(needle)),
  );
  const shownFittings = fittings.filter((f) => !needle || `${f.ship_type_name} ${f.name}`.toLowerCase().includes(needle));

  return (
    <div className="space-y-4 p-1">
      <div className="flex flex-wrap items-center gap-2">
        <Input placeholder="Search doctrines and ships" value={query} onChange={(e) => setQuery(e.target.value)} className="max-w-xs" />
        {config.canManage && (
          <Button size="sm" className="ml-auto" onClick={() => setImportOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Import EFT
          </Button>
        )}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Tabs defaultValue="doctrines">
        <TabsList>
          <TabsTrigger value="doctrines">Doctrines</TabsTrigger>
          <TabsTrigger value="fittings">Fittings</TabsTrigger>
          {config.canManage && <TabsTrigger value="settings">Settings</TabsTrigger>}
        </TabsList>
        <TabsContent value="doctrines" className="grid gap-4 lg:grid-cols-2">
          {shownDoctrines.map((d) => (
            <DoctrineCard key={d.id} doctrine={d} onOpenFitting={setOpenFitting} />
          ))}
          {!shownDoctrines.length && <p className="text-sm text-muted-foreground">No doctrines to show.</p>}
        </TabsContent>
        <TabsContent value="fittings">
          <FittingList fittings={shownFittings} onOpenFitting={setOpenFitting} />
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

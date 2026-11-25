import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { ComplianceOverviewResponse } from "@/types";

export function ComplianceView() {
  const [data, setData] = useState<ComplianceOverviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    api
      .complianceOverview()
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Coverage across {data?.total_members ?? 0} member accounts with linked characters.
        </p>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          <RefreshCw className={`mr-1 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      {data && (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            {data.doctrines.map((doc) => (
              <Card key={doc.id}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-base">
                    <span>{doc.name}</span>
                    <Badge variant="secondary">
                      {doc.ready_members}/{doc.total_members} ready
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {doc.roles.map((role) => (
                    <div key={role.role} className="space-y-1.5 rounded-md border border-border p-2.5">
                      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase text-muted-foreground">
                        <span>{role.role}</span>
                        <Badge className="bg-emerald-600 text-white">{role.green} full</Badge>
                        <Badge className="bg-amber-500 text-black">{role.yellow} min</Badge>
                        <Badge variant="destructive">{role.red} missing</Badge>
                        {role.unknown > 0 && <Badge variant="outline">{role.unknown} unknown</Badge>}
                      </div>
                      <ul className="space-y-1 text-sm">
                        {role.fittings.map((f) => (
                          <li key={f.fitting_id} className="flex flex-wrap items-center justify-between gap-2">
                            <span>
                              {f.ship_type_name} — <span className="text-muted-foreground">{f.fitting_name}</span>
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {f.green}G / {f.yellow}Y / {f.red}R
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                  {!doc.roles.length && <p className="text-sm text-muted-foreground">No fittings in doctrine.</p>}
                </CardContent>
              </Card>
            ))}
            {!data.doctrines.length && <p className="text-sm text-muted-foreground">No doctrines to evaluate.</p>}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Skill Gap Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              {data.gaps.length ? (
                <ul className="space-y-2 text-sm">
                  {data.gaps.map((g) => (
                    <li key={g.skill_id} className="flex items-center justify-between border-b border-border pb-1.5">
                      <span>{g.skill_name}</span>
                      <Badge variant="destructive">{g.blocked_members} blocked</Badge>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No blocking skills detected.</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

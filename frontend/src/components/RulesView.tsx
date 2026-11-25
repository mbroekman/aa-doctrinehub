import { useCallback, useEffect, useState } from "react";
import { Check, Play, Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type {
  AuditLogEntry,
  ComplianceRule,
  NotificationSettings,
  PendingApprovalItem,
  RuleConditionNode,
} from "@/types";

const CONDITION_TYPES = [
  { value: "can_fly_fitting", label: "Can fly fitting" },
  { value: "doctrine_coverage", label: "Doctrine coverage (%)" },
  { value: "skill", label: "Skill level" },
  { value: "total_sp", label: "Minimum Total SP" },
  { value: "ship_owned", label: "Ship owned in assets" },
  { value: "implant", label: "Implant active" },
  { value: "other_group", label: "Member of Auth group" },
  { value: "fleet_participation", label: "Fleet participation (FATs)" },
];

export function RulesView() {
  const [rules, setRules] = useState<ComplianceRule[]>([]);
  const [groups, setGroups] = useState<{ id: number; name: string }[]>([]);
  const [approvals, setApprovals] = useState<PendingApprovalItem[]>([]);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [notif, setNotif] = useState<NotificationSettings | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // New rule builder state
  const [name, setName] = useState("");
  const [groupId, setGroupId] = useState<number>(0);
  const [mode, setMode] = useState<ComplianceRule["mode"]>("report_only");
  const [op, setOp] = useState<"AND" | "OR" | "AT_LEAST">("AND");
  const [atLeastN, setAtLeastN] = useState(1);
  const [graceHours, setGraceHours] = useState(48);
  const [condType, setCondType] = useState("skill");
  const [condParam1, setCondParam1] = useState("20533");
  const [condParam2, setCondParam2] = useState("1");

  const load = useCallback(() => {
    setError("");
    Promise.all([api.rules(), api.approvals(), api.auditLogs(), api.notificationSettings()])
      .then(([r, a, l, n]) => {
        setRules(r.rules);
        setGroups(r.groups);
        if (!groupId && r.groups.length) setGroupId(r.groups[0].id);
        setApprovals(a.approvals);
        setLogs(l.logs);
        setNotif(n);
      })
      .catch((e: Error) => setError(e.message));
  }, [groupId]);

  useEffect(load, [load]);

  const buildLeaf = (): RuleConditionNode => {
    if (condType === "can_fly_fitting") return { type: "can_fly_fitting", fitting_id: Number(condParam1), level: "minimum" };
    if (condType === "doctrine_coverage") return { type: "doctrine_coverage", doctrine_id: Number(condParam1), min_required_pct: Number(condParam2) || 100 };
    if (condType === "skill") return { type: "skill", skill_id: Number(condParam1), min_level: Number(condParam2) || 1 };
    if (condType === "total_sp") return { type: "total_sp", min_sp: Number(condParam1) || 10000000 };
    if (condType === "ship_owned") return { type: "ship_owned", ship_type_id: Number(condParam1), min_count: Number(condParam2) || 1 };
    if (condType === "implant") return { type: "implant", type_name: condParam1 };
    if (condType === "other_group") return { type: "other_group", group_name: condParam1 };
    return { type: "fleet_participation", days: Number(condParam1) || 30, min_fats: Number(condParam2) || 1 };
  };

  const handleCreate = async () => {
    if (!name.trim() || !groupId) return;
    setBusy(true);
    try {
      const tree: RuleConditionNode = {
        op,
        ...(op === "AT_LEAST" ? { n: atLeastN } : {}),
        children: [buildLeaf()],
      };
      await api.createRule({
        name: name.trim(),
        group_id: groupId,
        mode,
        grace_period_hours: graceHours,
        condition_tree: tree,
      });
      setName("");
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const handleEvaluate = async () => {
    setBusy(true);
    try {
      await api.evaluateRules();
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Compliance rules evaluate all linked characters of each account before granting or revoking Auth groups.
        </p>
        <Button size="sm" onClick={handleEvaluate} disabled={busy}>
          <Play className="mr-1 h-3.5 w-3.5" />
          Evaluate All Rules
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Rule Builder</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <Input placeholder="Rule name (e.g. SIG: Logistics)" value={name} onChange={(e) => setName(e.target.value)} />
              <select
                value={groupId}
                onChange={(e) => setGroupId(Number(e.target.value))}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as ComplianceRule["mode"])}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="report_only">Report only</option>
                <option value="automatic">Automatic</option>
                <option value="reviewer_approval">Reviewer approval</option>
              </select>
              <select
                value={op}
                onChange={(e) => setOp(e.target.value as "AND" | "OR" | "AT_LEAST")}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="AND">AND (all match)</option>
                <option value="OR">OR (any matches)</option>
                <option value="AT_LEAST">At least N</option>
              </select>
              <Input
                type="number"
                min={1}
                value={op === "AT_LEAST" ? atLeastN : graceHours}
                onChange={(e) =>
                  op === "AT_LEAST" ? setAtLeastN(Number(e.target.value)) : setGraceHours(Number(e.target.value))
                }
                placeholder={op === "AT_LEAST" ? "N" : "Grace (h)"}
                title={op === "AT_LEAST" ? "Minimum matching conditions" : "Grace period in hours"}
              />
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              <select
                value={condType}
                onChange={(e) => setCondType(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                {CONDITION_TYPES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
              <Input
                value={condParam1}
                onChange={(e) => setCondParam1(e.target.value)}
                placeholder="ID / Name / Days"
              />
              <Input
                value={condParam2}
                onChange={(e) => setCondParam2(e.target.value)}
                placeholder="Level / Count / %"
              />
            </div>
            <Button size="sm" onClick={handleCreate} disabled={busy || !name.trim()}>
              <Plus className="mr-1 h-3.5 w-3.5" />
              Create Rule
            </Button>
          </CardContent>
        </Card>

        {notif && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Discord Notifications & Language</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Input
                placeholder="Discord webhook URL"
                value={notif.discord_webhook_url}
                onChange={(e) => setNotif({ ...notif, discord_webhook_url: e.target.value })}
              />
              <div className="flex flex-wrap items-center gap-3">
                <select
                  value={notif.discord_language}
                  onChange={(e) => setNotif({ ...notif, discord_language: e.target.value })}
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                >
                  {notif.language_choices.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.label}
                    </option>
                  ))}
                </select>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={notif.dm_warnings_enabled}
                    onChange={(e) => setNotif({ ...notif, dm_warnings_enabled: e.target.checked })}
                  />
                  Send DM warning before revocation
                </label>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void api.saveNotificationSettings(notif).then(setNotif)}
              >
                Save Notification Settings
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active Rules ({rules.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {rules.map((r) => (
            <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2.5 text-sm">
              <div>
                <div className="font-medium">
                  {r.name} <span className="text-muted-foreground">→ {r.group_name}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  Mode: {r.mode} · Grace: {r.grace_period_hours}h · Pass {r.summary.pass} / Fail {r.summary.fail} / Unknown {r.summary.unknown}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={r.mode}
                  onChange={(e) =>
                    void api.updateRule(r.id, { mode: e.target.value as ComplianceRule["mode"] }).then(load)
                  }
                  className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                >
                  <option value="report_only">Report only</option>
                  <option value="automatic">Automatic</option>
                  <option value="reviewer_approval">Reviewer approval</option>
                </select>
                <Button size="sm" variant="ghost" onClick={() => void api.deleteRule(r.id).then(load)}>
                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Pending Reviewer Approvals ({approvals.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {approvals.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-2 rounded-md border border-border p-2 text-sm">
                <div>
                  <span className="font-medium">{a.username}</span>{" "}
                  <Badge variant={a.action === "grant" ? "default" : "destructive"}>{a.action}</Badge>{" "}
                  <span>{a.group_name}</span>
                  <div className="text-xs text-muted-foreground">{a.reason}</div>
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant="outline" onClick={() => void api.decideApproval(a.id, true).then(load)}>
                    <Check className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => void api.decideApproval(a.id, false).then(load)}>
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
            {!approvals.length && <p className="text-sm text-muted-foreground">No pending approvals.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Audit Log</CardTitle>
          </CardHeader>
          <CardContent className="max-h-64 space-y-1.5 overflow-y-auto text-xs">
            {logs.map((l) => (
              <div key={l.id} className="border-b border-border pb-1">
                <span className="font-semibold">{l.action.toUpperCase()}</span> {l.group_name} for{" "}
                <span className="font-medium">{l.username}</span> (by {l.actor})
                {l.reason && <div className="text-muted-foreground">{l.reason}</div>}
              </div>
            ))}
            {!logs.length && <p className="text-sm text-muted-foreground">No audit entries yet.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

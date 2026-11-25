import { useCallback, useEffect, useState } from "react";
import { Check, Copy, Pencil, Play, Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type {
  AuditLogEntry,
  ComplianceRule,
  Doctrine,
  FittingSummary,
  NotificationSettings,
  PendingApprovalItem,
  RuleConditionNode,
} from "@/types";

const CONDITION_TYPES = [
  { value: "can_fly_fitting", label: "Can fly fitting" },
  { value: "doctrine_coverage", label: "Doctrine coverage (%)" },
  { value: "skill", label: "Specific skill level" },
  { value: "total_sp", label: "Minimum Total SP" },
  { value: "ship_owned", label: "Ship owned in assets" },
  { value: "implant", label: "Implant active" },
  { value: "other_group", label: "Member of Auth group" },
  { value: "fleet_participation", label: "Fleet participation (FATs)" },
];

interface DraftCondition {
  type: string;
  fittingId: number;
  fittingLevel: "minimum" | "recommended";
  doctrineId: number;
  doctrineFittingId: number;
  minPct: number;
  skillId: number;
  minSkillLevel: number;
  minSp: number;
  shipTypeId: number;
  minCount: number;
  implantName: string;
  otherGroupId: number;
  days: number;
  minFats: number;
}

function makeDefaultCondition(
  doctrines: Doctrine[],
  fittings: FittingSummary[],
  groups: { id: number; name: string }[],
): DraftCondition {
  return {
    type: fittings.length ? "can_fly_fitting" : doctrines.length ? "doctrine_coverage" : "skill",
    fittingId: fittings[0]?.id ?? 0,
    fittingLevel: "minimum",
    doctrineId: doctrines[0]?.id ?? 0,
    doctrineFittingId: 0,
    minPct: 100,
    skillId: 20533,
    minSkillLevel: 1,
    minSp: 15000000,
    shipTypeId: fittings[0]?.ship_type_id ?? 0,
    minCount: 1,
    implantName: "",
    otherGroupId: groups[0]?.id ?? 0,
    days: 30,
    minFats: 1,
  };
}

function toConditionNode(c: DraftCondition): RuleConditionNode {
  switch (c.type) {
    case "can_fly_fitting":
      return { type: "can_fly_fitting", fitting_id: c.fittingId, level: c.fittingLevel };
    case "doctrine_coverage":
      return c.doctrineFittingId > 0
        ? { type: "doctrine_coverage", doctrine_id: c.doctrineId, fitting_id: c.doctrineFittingId, level: c.fittingLevel }
        : { type: "doctrine_coverage", doctrine_id: c.doctrineId, min_required_pct: c.minPct };
    case "skill":
      return { type: "skill", skill_id: c.skillId, min_level: c.minSkillLevel };
    case "total_sp":
      return { type: "total_sp", min_sp: c.minSp };
    case "ship_owned":
      return { type: "ship_owned", ship_type_id: c.shipTypeId, min_count: c.minCount };
    case "implant":
      return { type: "implant", type_name: c.implantName };
    case "other_group":
      return { type: "other_group", group_id: c.otherGroupId };
    default:
      return { type: "fleet_participation", days: c.days, min_fats: c.minFats };
  }
}

function fromConditionNode(
  node: RuleConditionNode,
  doctrines: Doctrine[],
  fittings: FittingSummary[],
  groups: { id: number; name: string }[],
): DraftCondition {
  const base = makeDefaultCondition(doctrines, fittings, groups);
  const t = String(node.type || base.type);
  return {
    ...base,
    type: t,
    fittingId: Number(node.fitting_id ?? base.fittingId),
    fittingLevel: node.level === "recommended" ? "recommended" : "minimum",
    doctrineId: Number(node.doctrine_id ?? base.doctrineId),
    doctrineFittingId: Number(node.fitting_id ?? 0),
    minPct: Number(node.min_required_pct ?? base.minPct),
    skillId: Number(node.skill_id ?? base.skillId),
    minSkillLevel: Number(node.min_level ?? base.minSkillLevel),
    minSp: Number(node.min_sp ?? base.minSp),
    shipTypeId: Number(node.ship_type_id ?? base.shipTypeId),
    minCount: Number(node.min_count ?? base.minCount),
    implantName: String(node.type_name ?? ""),
    otherGroupId: Number(node.group_id ?? base.otherGroupId),
    days: Number(node.days ?? base.days),
    minFats: Number(node.min_fats ?? base.minFats),
  };
}

function parseConditionTree(
  tree: RuleConditionNode,
  doctrines: Doctrine[],
  fittings: FittingSummary[],
  groups: { id: number; name: string }[],
): { op: "AND" | "OR" | "AT_LEAST"; n: number; conditions: DraftCondition[] } {
  const rawOp = String(tree.op || "AND").toUpperCase();
  const op: "AND" | "OR" | "AT_LEAST" =
    rawOp === "OR" ? "OR" : rawOp === "AT_LEAST" ? "AT_LEAST" : "AND";
  const n = Number(tree.n ?? 1);
  const rawChildren = Array.isArray(tree.children) && tree.children.length
    ? tree.children
    : tree.type
      ? [tree]
      : [];
  const conditions = rawChildren.length
    ? rawChildren.map((ch) => fromConditionNode(ch, doctrines, fittings, groups))
    : [makeDefaultCondition(doctrines, fittings, groups)];
  return { op, n, conditions };
}

export function RulesView({
  doctrines,
  fittings,
}: {
  doctrines: Doctrine[];
  fittings: FittingSummary[];
}) {
  const [rules, setRules] = useState<ComplianceRule[]>([]);
  const [groups, setGroups] = useState<{ id: number; name: string }[]>([]);
  const [approvals, setApprovals] = useState<PendingApprovalItem[]>([]);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [notif, setNotif] = useState<NotificationSettings | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [groupId, setGroupId] = useState<number>(0);
  const [mode, setMode] = useState<ComplianceRule["mode"]>("report_only");
  const [op, setOp] = useState<"AND" | "OR" | "AT_LEAST">("AND");
  const [atLeastN, setAtLeastN] = useState(1);
  const [graceHours, setGraceHours] = useState(48);
  const [conditions, setConditions] = useState<DraftCondition[]>(() => [
    makeDefaultCondition(doctrines, fittings, []),
  ]);

  const resetBuilder = () => {
    setEditingRuleId(null);
    setName("");
    setMode("report_only");
    setOp("AND");
    setAtLeastN(1);
    setGraceHours(48);
    setConditions([makeDefaultCondition(doctrines, fittings, groups)]);
  };

  const loadIntoBuilder = (rule: ComplianceRule, asCopy: boolean) => {
    const parsed = parseConditionTree(rule.condition_tree || {}, doctrines, fittings, groups);
    setEditingRuleId(asCopy ? null : rule.id);
    setName(asCopy ? `${rule.name} (copy)` : rule.name);
    setGroupId(rule.group_id);
    setMode(asCopy ? "report_only" : rule.mode);
    setOp(parsed.op);
    setAtLeastN(parsed.n);
    setGraceHours(rule.grace_period_hours);
    setConditions(parsed.conditions);
  };

  const [skillQuery, setSkillQuery] = useState("");
  const [skillOptions, setSkillOptions] = useState<{ id: number; name: string }[]>([]);
  const [fittingQuery, setFittingQuery] = useState("");
  const [doctrineQuery, setDoctrineQuery] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api.searchSkills(skillQuery).then(setSkillOptions).catch(() => undefined);
    }, 150);
    return () => window.clearTimeout(timer);
  }, [skillQuery]);

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

  const updateCond = (idx: number, patch: Partial<DraftCondition>) => {
    setConditions((prev) => prev.map((item, i) => (i === idx ? { ...item, ...patch } : item)));
  };

  const handleSaveRule = async () => {
    if (!name.trim() || !groupId || !conditions.length) return;
    setBusy(true);
    try {
      const tree: RuleConditionNode = {
        op,
        ...(op === "AT_LEAST" ? { n: Math.min(atLeastN, conditions.length) } : {}),
        children: conditions.map(toConditionNode),
      };
      const payload = {
        name: name.trim(),
        group_id: groupId,
        mode,
        grace_period_hours: graceHours,
        condition_tree: tree,
      };
      if (editingRuleId !== null) {
        await api.updateRule(editingRuleId, payload);
      } else {
        await api.createRule(payload);
      }
      resetBuilder();
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
            <CardTitle className="text-base">
              {editingRuleId !== null ? "Edit Rule" : "Rule Builder"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Rule name</label>
                <Input placeholder="e.g. SIG: Logistics" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Auth group to grant</label>
                <select
                  value={groupId}
                  onChange={(e) => setGroupId(Number(e.target.value))}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  {groups.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Action mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as ComplianceRule["mode"])}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="report_only">Report only</option>
                  <option value="automatic">Automatic</option>
                  <option value="reviewer_approval">Reviewer approval</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Combine conditions</label>
                <select
                  value={op}
                  onChange={(e) => setOp(e.target.value as "AND" | "OR" | "AT_LEAST")}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="AND">AND (all must match)</option>
                  <option value="OR">OR (any must match)</option>
                  <option value="AT_LEAST">At least N must match</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Grace period (hours)</label>
                <Input
                  type="number"
                  min={1}
                  value={graceHours}
                  onChange={(e) => setGraceHours(Number(e.target.value))}
                />
              </div>
            </div>

            {op === "AT_LEAST" && (
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">
                  Minimum matching conditions (N)
                </label>
                <Input
                  type="number"
                  min={1}
                  max={Math.max(1, conditions.length)}
                  value={atLeastN}
                  onChange={(e) => setAtLeastN(Number(e.target.value))}
                  className="w-32"
                />
              </div>
            )}

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">Conditions</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    setConditions((prev) => [...prev, makeDefaultCondition(doctrines, fittings, groups)])
                  }
                >
                  <Plus className="mr-1 h-3.5 w-3.5" />
                  Add condition
                </Button>
              </div>

              {conditions.map((cond, idx) => (
                <div key={idx} className="space-y-2 rounded-md border border-border p-2.5">
                  <div className="flex items-center gap-2">
                    <select
                      value={cond.type}
                      onChange={(e) => updateCond(idx, { type: e.target.value })}
                      className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm"
                    >
                      {CONDITION_TYPES.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                    {conditions.length > 1 && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setConditions((prev) => prev.filter((_, i) => i !== idx))}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    )}
                  </div>

                  {cond.type === "can_fly_fitting" && (
                    <div className="grid gap-2 sm:grid-cols-3">
                      <div className="space-y-1 sm:col-span-2">
                        <label className="text-xs text-muted-foreground">Fitting</label>
                        <Input
                          placeholder="Search fitting or ship..."
                          value={fittingQuery}
                          onChange={(e) => setFittingQuery(e.target.value)}
                          className="h-8 text-xs"
                        />
                        <select
                          value={cond.fittingId}
                          onChange={(e) => updateCond(idx, { fittingId: Number(e.target.value) })}
                          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        >
                          {fittings
                            .filter((f) => {
                              const q = fittingQuery.trim().toLowerCase();
                              return !q || `${f.ship_type_name} ${f.name}`.toLowerCase().includes(q);
                            })
                            .map((f) => (
                              <option key={f.id} value={f.id}>
                                {f.ship_type_name} — {f.name}
                              </option>
                            ))}
                          {!fittings.length && <option value={0}>No fittings available</option>}
                        </select>
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">Skill target</label>
                        <select
                          value={cond.fittingLevel}
                          onChange={(e) =>
                            updateCond(idx, { fittingLevel: e.target.value as "minimum" | "recommended" })
                          }
                          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        >
                          <option value="minimum">Minimum</option>
                          <option value="recommended">Recommended</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {cond.type === "doctrine_coverage" && (() => {
                    const selectedDoc = doctrines.find((d) => d.id === cond.doctrineId);
                    const docFittings = selectedDoc?.fittings ?? [];
                    return (
                      <div className="space-y-2">
                        <div className="grid gap-2 sm:grid-cols-2">
                          <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">Doctrine</label>
                            <Input
                              placeholder="Search doctrine..."
                              value={doctrineQuery}
                              onChange={(e) => setDoctrineQuery(e.target.value)}
                              className="h-8 text-xs"
                            />
                            <select
                              value={cond.doctrineId}
                              onChange={(e) =>
                                updateCond(idx, { doctrineId: Number(e.target.value), doctrineFittingId: 0 })
                              }
                              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                            >
                              {doctrines
                                .filter((d) => {
                                  const q = doctrineQuery.trim().toLowerCase();
                                  return !q || d.name.toLowerCase().includes(q);
                                })
                                .map((d) => (
                                  <option key={d.id} value={d.id}>
                                    {d.name}
                                  </option>
                                ))}
                              {!doctrines.length && <option value={0}>No doctrines available</option>}
                            </select>
                          </div>
                          <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">Doctrine scope (All or specific fit)</label>
                            <select
                              value={cond.doctrineFittingId}
                              onChange={(e) => updateCond(idx, { doctrineFittingId: Number(e.target.value) })}
                              className="mt-9 h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                            >
                              <option value={0}>All required fittings (%)</option>
                              {docFittings.map((df) => (
                                <option key={df.id} value={df.id}>
                                  {df.ship_type_name} — {df.name}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                        {cond.doctrineFittingId > 0 ? (
                          <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">Skill target</label>
                            <select
                              value={cond.fittingLevel}
                              onChange={(e) =>
                                updateCond(idx, { fittingLevel: e.target.value as "minimum" | "recommended" })
                              }
                              className="h-9 w-48 rounded-md border border-input bg-background px-3 text-sm"
                            >
                              <option value="minimum">Minimum</option>
                              <option value="recommended">Recommended</option>
                            </select>
                          </div>
                        ) : (
                          <div className="space-y-1">
                            <label className="text-xs text-muted-foreground">Required coverage (%)</label>
                            <Input
                              type="number"
                              min={1}
                              max={100}
                              value={cond.minPct}
                              onChange={(e) => updateCond(idx, { minPct: Number(e.target.value) })}
                              className="w-32"
                            />
                          </div>
                        )}
                      </div>
                    );
                  })()}

                  {cond.type === "skill" && (
                    <div className="grid gap-2 sm:grid-cols-3">
                      <div className="space-y-1 sm:col-span-2">
                        <label className="text-xs text-muted-foreground">Skill</label>
                        <Input
                          placeholder="Search skill by name or ID..."
                          value={skillQuery}
                          onChange={(e) => setSkillQuery(e.target.value)}
                          className="h-8 text-xs"
                        />
                        <select
                          value={cond.skillId}
                          onChange={(e) => updateCond(idx, { skillId: Number(e.target.value) })}
                          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        >
                          {!skillOptions.some((s) => s.id === cond.skillId) && cond.skillId > 0 && (
                            <option value={cond.skillId}>Skill #{cond.skillId}</option>
                          )}
                          {skillOptions.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name} ({s.id})
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">Minimum level (1–5)</label>
                        <Input
                          type="number"
                          min={1}
                          max={5}
                          value={cond.minSkillLevel}
                          onChange={(e) => updateCond(idx, { minSkillLevel: Number(e.target.value) })}
                        />
                      </div>
                    </div>
                  )}

                  {cond.type === "total_sp" && (
                    <div className="space-y-1">
                      <label className="text-xs text-muted-foreground">Minimum Total Skillpoints</label>
                      <Input
                        type="number"
                        min={0}
                        step={1000000}
                        value={cond.minSp}
                        onChange={(e) => updateCond(idx, { minSp: Number(e.target.value) })}
                      />
                    </div>
                  )}

                  {cond.type === "ship_owned" && (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">Ship Type ID</label>
                        <Input
                          type="number"
                          value={cond.shipTypeId}
                          onChange={(e) => updateCond(idx, { shipTypeId: Number(e.target.value) })}
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">Minimum hulls owned</label>
                        <Input
                          type="number"
                          min={1}
                          value={cond.minCount}
                          onChange={(e) => updateCond(idx, { minCount: Number(e.target.value) })}
                        />
                      </div>
                    </div>
                  )}

                  {cond.type === "implant" && (
                    <div className="space-y-1">
                      <label className="text-xs text-muted-foreground">Implant name (contains)</label>
                      <Input
                        placeholder="e.g. High-grade Amulet"
                        value={cond.implantName}
                        onChange={(e) => updateCond(idx, { implantName: e.target.value })}
                      />
                    </div>
                  )}

                  {cond.type === "other_group" && (
                    <div className="space-y-1">
                      <label className="text-xs text-muted-foreground">Required Auth group</label>
                      <select
                        value={cond.otherGroupId}
                        onChange={(e) => updateCond(idx, { otherGroupId: Number(e.target.value) })}
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                      >
                        {groups.map((g) => (
                          <option key={g.id} value={g.id}>
                            {g.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {cond.type === "fleet_participation" && (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">Lookback window (days)</label>
                        <Input
                          type="number"
                          min={1}
                          value={cond.days}
                          onChange={(e) => updateCond(idx, { days: Number(e.target.value) })}
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs text-muted-foreground">Minimum FATs</label>
                        <Input
                          type="number"
                          min={1}
                          value={cond.minFats}
                          onChange={(e) => updateCond(idx, { minFats: Number(e.target.value) })}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={handleSaveRule} disabled={busy || !name.trim()}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                {editingRuleId !== null ? "Save Changes" : "Create Rule"}
              </Button>
              {editingRuleId !== null && (
                <Button size="sm" variant="outline" onClick={resetBuilder} disabled={busy}>
                  Cancel
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {notif && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Discord Notifications &amp; Language</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Discord webhook URL</label>
                <Input
                  placeholder="https://discord.com/api/webhooks/..."
                  value={notif.discord_webhook_url}
                  onChange={(e) => setNotif({ ...notif, discord_webhook_url: e.target.value })}
                />
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="space-y-1">
                  <label className="block text-xs font-medium text-muted-foreground">Channel message language</label>
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
                </div>
                <label className="mt-5 flex items-center gap-2 text-sm">
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
                <Button size="sm" variant="outline" onClick={() => loadIntoBuilder(r, false)} title="Edit rule">
                  <Pencil className="mr-1 h-3.5 w-3.5" />
                  Edit
                </Button>
                <Button size="sm" variant="outline" onClick={() => loadIntoBuilder(r, true)} title="Copy rule">
                  <Copy className="mr-1 h-3.5 w-3.5" />
                  Copy
                </Button>
                <Button size="sm" variant="ghost" onClick={() => void api.deleteRule(r.id).then(load)} title="Delete rule">
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

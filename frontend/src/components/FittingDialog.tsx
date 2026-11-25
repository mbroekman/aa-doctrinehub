import { useEffect, useState } from "react";
import { Copy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ShipIcon } from "@/components/ShipIcon";
import { SourceBadge } from "@/components/SourceBadge";
import { api } from "@/lib/api";
import type { FittingDetail, FittingEligibilityResponse, FittingItem, TrafficLight } from "@/types";

const SECTIONS: { prefix: string; label: string }[] = [
  { prefix: "HiSlot", label: "High slots" },
  { prefix: "MedSlot", label: "Mid slots" },
  { prefix: "LoSlot", label: "Low slots" },
  { prefix: "RigSlot", label: "Rigs" },
  { prefix: "SubSystemSlot", label: "Subsystems" },
  { prefix: "ServiceSlot", label: "Service slots" },
  { prefix: "FighterBay", label: "Fighters" },
  { prefix: "DroneBay", label: "Drones" },
  { prefix: "Cargo", label: "Cargo" },
];

function itemsFor(items: FittingItem[], prefix: string) {
  return items.filter((i) => i.flag.replace(/\d+$/, "") === prefix);
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      <Copy className="mr-1 h-3.5 w-3.5" />
      {copied ? "Copied" : label}
    </Button>
  );
}

const LIGHT_STYLE: Record<TrafficLight, { label: string; className: string }> = {
  green: { label: "Can fly (Recommended)", className: "bg-emerald-600 text-white" },
  yellow: { label: "Can fly (Minimum)", className: "bg-amber-500 text-black" },
  red: { label: "Missing skills", className: "bg-destructive text-destructive-foreground" },
  unknown: { label: "Skills unknown", className: "bg-secondary text-secondary-foreground" },
};

export function FittingDialog({ fittingId, onClose }: { fittingId: number | null; onClose: () => void }) {
  const [fitting, setFitting] = useState<FittingDetail | null>(null);
  const [elig, setElig] = useState<FittingEligibilityResponse | null>(null);
  const [skillPlan, setSkillPlan] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (fittingId === null) return;
    setFitting(null);
    setElig(null);
    setSkillPlan("");
    setError("");
    api.fitting(fittingId).then(setFitting).catch((e: Error) => setError(e.message));
    api.fittingEligibility(fittingId).then(setElig).catch(() => undefined);
    api
      .fittingSkillPlan(fittingId, "minimum")
      .then((res) => setSkillPlan(res.skill_plan))
      .catch(() => undefined);
  }, [fittingId]);

  return (
    <Dialog open={fittingId !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {fitting ? (
              <span className="flex items-center gap-2">
                <ShipIcon typeId={fitting.ship_type_id} />
                {fitting.ship_type_name}: {fitting.name}
                <SourceBadge source={fitting.source} />
              </span>
            ) : (
              "Fitting"
            )}
          </DialogTitle>
        </DialogHeader>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {fitting?.version && (
          <div className="space-y-4">
            {fitting.description && <p className="text-sm text-muted-foreground">{fitting.description}</p>}
            <div className="flex flex-wrap items-center gap-2">
              <CopyButton text={fitting.version.eft} label="Copy EFT" />
              <CopyButton text={fitting.version.multibuy} label="Copy multibuy" />
              {skillPlan && <CopyButton text={skillPlan} label="Copy Skill Plan" />}
              {elig && (
                <Badge className={LIGHT_STYLE[elig.status].className}>{LIGHT_STYLE[elig.status].label}</Badge>
              )}
            </div>
            {elig && elig.characters.length > 0 && (
              <div className="rounded-md border border-border p-2 text-xs">
                <div className="mb-1 font-semibold uppercase text-muted-foreground">Character Eligibility</div>
                <div className="flex flex-wrap gap-2">
                  {elig.characters.map((c) => (
                    <Badge key={c.character_id} className={LIGHT_STYLE[c.status].className}>
                      {c.character_name}: {c.status.toUpperCase()}
                    </Badge>
                  ))}
                </div>
                {elig.missing_required.length > 0 && (
                  <p className="mt-1.5 text-destructive">
                    Missing:{" "}
                    {elig.missing_required
                      .map((m) => `${m.skill_name} ${m.required_level} (have ${m.current_level})`)
                      .join(", ")}
                  </p>
                )}
              </div>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              {SECTIONS.map(({ prefix, label }) => {
                const items = itemsFor(fitting.version!.items, prefix);
                if (!items.length) return null;
                return (
                  <div key={prefix}>
                    <div className="mb-1 text-xs font-semibold uppercase text-muted-foreground">{label}</div>
                    <ul className="space-y-0.5 text-sm">
                      {items.map((item, index) => (
                        <li key={`${item.flag}-${index}`} className={item.is_offline ? "opacity-60" : ""}>
                          {item.quantity > 1 ? `${item.quantity}x ` : ""}
                          {item.type_name}
                          {item.charge_name && <span className="text-muted-foreground">, {item.charge_name}</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground">
              Version {fitting.version.number}
              {fitting.version.change_note ? `: ${fitting.version.change_note}` : ""}
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

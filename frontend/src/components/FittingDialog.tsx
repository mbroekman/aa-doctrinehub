import { useEffect, useState } from "react";
import { Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ShipIcon } from "@/components/ShipIcon";
import { SourceBadge } from "@/components/SourceBadge";
import { api } from "@/lib/api";
import type { FittingDetail, FittingItem } from "@/types";

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

export function FittingDialog({ fittingId, onClose }: { fittingId: number | null; onClose: () => void }) {
  const [fitting, setFitting] = useState<FittingDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (fittingId === null) return;
    setFitting(null);
    setError("");
    api.fitting(fittingId).then(setFitting).catch((e: Error) => setError(e.message));
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
            <div className="flex flex-wrap gap-2">
              <CopyButton text={fitting.version.eft} label="Copy EFT" />
              <CopyButton text={fitting.version.multibuy} label="Copy multibuy" />
            </div>
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

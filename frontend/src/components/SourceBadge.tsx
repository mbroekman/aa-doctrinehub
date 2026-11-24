import { Badge } from "@/components/ui/badge";
import type { Source } from "@/types";

/** Marks records synced from another app, so they stand out next to our own. */
export function SourceBadge({ source }: { source: Source }) {
  if (source === "local") return null;
  return (
    <Badge variant="outline" title="Synced from the Fittings app; read-only here">
      Fittings
    </Badge>
  );
}

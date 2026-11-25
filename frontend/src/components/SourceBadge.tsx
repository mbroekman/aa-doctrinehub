import { Badge } from "@/components/ui/badge";
import type { Source } from "@/types";

/** Marks records synced from another app, so they stand out next to our own. */
export function SourceBadge({ source }: { source: Source }) {
  if (source === "local") return null;
  if (source === "remote_auth") {
    return (
      <Badge variant="outline" title="Scraped from an external Alliance Auth; read-only here">
        External Auth
      </Badge>
    );
  }
  return (
    <Badge variant="outline" title="Synced from the Fittings app; read-only here">
      Fittings
    </Badge>
  );
}

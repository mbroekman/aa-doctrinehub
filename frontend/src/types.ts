export type Source = "local" | "fittings" | "remote_auth";

export interface CategoryRef {
  id: number;
  name: string;
  color: string;
  source: Source;
}

export interface FittingSummary {
  id: number;
  name: string;
  ship_type_id: number | null;
  ship_type_name: string;
  source: Source;
  is_editable: boolean;
  categories: CategoryRef[];
}

export interface DoctrineFittingRef extends FittingSummary {
  role: string;
  is_required: boolean;
  target_count: number | null;
}

export interface Doctrine {
  id: number;
  name: string;
  description: string;
  icon_url: string;
  status: "draft" | "active" | "phasing_out" | "archived";
  source: Source;
  is_editable: boolean;
  last_synced_at: string | null;
  categories: CategoryRef[];
  fittings: DoctrineFittingRef[];
}

export interface FittingItem {
  flag: string;
  type_id: number | null;
  type_name: string;
  quantity: number;
  charge_name: string;
  is_offline: boolean;
}

export interface FittingDetail extends FittingSummary {
  description: string;
  version: {
    number: number;
    created_at: string;
    change_note: string;
    eft: string;
    multibuy: string;
    items: FittingItem[];
  } | null;
}

export interface SyncSettings {
  fittings_app_installed: boolean;
  fittings_sync_enabled: boolean;
  fittings_sync_interval_days: number;
  fittings_last_sync_at: string | null;
  fittings_last_sync_summary: string;
}

export interface RemoteScrapePreview {
  mode: "preview";
  doctrines_total: number;
  doctrines_already_imported: number;
  doctrines_count: number;
  doctrines_new: number;
  doctrines_existing: number;
  fittings_total: number;
  fittings_already_imported: number;
  fittings_count: number;
  fittings_new: number;
  fittings_existing: number;
  categories_total: number;
  categories_already_imported: number;
  categories_count: number;
  categories_new: number;
  categories_existing: number;
  doctrines: {
    external_id: number;
    name: string;
    fittings_count: number | null;
    is_new: boolean;
  }[];
}

export interface RemoteScrapeImportResult {
  mode: "import";
  summary: string;
  fittings_created: number;
  fittings_updated: number;
  fittings_removed: number;
  doctrines_created: number;
  doctrines_updated: number;
  doctrines_archived: number;
  categories_synced: number;
  total_doctrines_stored: number;
  total_fittings_stored: number;
  total_categories_stored: number;
  doctrines: {
    external_id: number;
    name: string;
    fittings_count: number;
  }[];
}

export interface RemoteScrapePurgeResult {
  ok: boolean;
  doctrines_deleted: number;
  fittings_deleted: number;
  categories_deleted: number;
}

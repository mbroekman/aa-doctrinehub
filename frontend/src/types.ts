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

export type TrafficLight = "green" | "yellow" | "red" | "unknown";

export interface CharacterLinkStatus {
  character_id: number;
  character_name: string;
  has_valid_token: boolean;
  sync_status: "pending" | "ok" | "error";
  last_synced_at: string | null;
  last_error: string;
  total_sp: number;
}

export interface EligibilityStatusResponse {
  all_linked: boolean;
  characters: CharacterLinkStatus[];
}

export interface SkillRequirement {
  id: number;
  skill_id: number;
  skill_name: string;
  required_level: number;
  recommended_level: number;
  source: "dogma" | "manual";
}

export interface MissingSkill {
  skill_id: number;
  skill_name: string;
  current_level: number;
  required_level: number;
  recommended_level: number;
}

export interface CharacterFittingEligibility {
  character_id: number;
  character_name: string;
  status: TrafficLight;
  missing_required: MissingSkill[];
  missing_recommended: MissingSkill[];
  met_required: number;
  total_requirements: number;
}

export interface FittingEligibilityResponse {
  status: TrafficLight;
  best_character_id: number | null;
  best_character_name: string | null;
  missing_required: MissingSkill[];
  missing_recommended: MissingSkill[];
  met_required: number;
  total_requirements: number;
  characters: CharacterFittingEligibility[];
  requirements: SkillRequirement[];
}

export interface ComplianceOverviewResponse {
  total_members: number;
  doctrines: {
    id: number;
    name: string;
    total_members: number;
    ready_members: number;
    roles: {
      role: string;
      green: number;
      yellow: number;
      red: number;
      unknown: number;
      fittings: {
        fitting_id: number;
        fitting_name: string;
        ship_type_name: string;
        is_required: boolean;
        target_count: number | null;
        green: number;
        yellow: number;
        red: number;
        unknown: number;
      }[];
    }[];
  }[];
  gaps: {
    skill_id: number;
    skill_name: string;
    blocked_members: number;
  }[];
}

export interface RuleConditionNode {
  op?: "AND" | "OR" | "AT_LEAST";
  n?: number;
  children?: RuleConditionNode[];
  type?: string;
  [key: string]: unknown;
}

export interface ComplianceRule {
  id: number;
  name: string;
  description: string;
  group_id: number;
  group_name: string;
  mode: "report_only" | "automatic" | "reviewer_approval";
  is_active: boolean;
  grace_period_hours: number;
  condition_tree: RuleConditionNode;
  summary: {
    pass: number;
    fail: number;
    unknown: number;
  };
  evaluations?: {
    username: string;
    status: "pass" | "fail" | "unknown";
    reasons: string[];
    grace_until: string | null;
    evaluated_at: string | null;
  }[];
}

export interface PendingApprovalItem {
  id: number;
  rule_id: number;
  rule_name: string;
  group_name: string;
  user_id: number;
  username: string;
  action: "grant" | "revoke";
  reason: string;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  rule_name: string;
  username: string;
  group_name: string;
  action: string;
  reason: string;
  actor: string;
  created_at: string;
}

export interface NotificationSettings {
  discord_webhook_url: string;
  discord_language: string;
  dm_warnings_enabled: boolean;
  language_choices: { code: string; label: string }[];
}

export interface HangarShipMatch {
  character_id: number;
  character_name: string;
  item_id: number;
  location_id: number;
  location_name: string;
  ship_type_id: number;
  ship_type_name: string;
  fitting_id: number;
  fitting_name: string;
  doctrine_names: string[];
  match_status: "full" | "partial" | "hull_only";
  match_pct: number;
}

export interface IndustryOrderResult {
  pushed: number;
  order_id?: number;
  message: string;
  shortages: {
    fitting_id: number;
    fitting_name: string;
    ship_type_id: number | null;
    ship_type_name: string;
    target_count: number;
    owned_count: number;
    shortage: number;
  }[];
}

export interface SrpCompareResult {
  hull_match: boolean;
  killmail_ship_type_id: number;
  expected_ship_type_id: number | null;
  compliance_pct: number;
  matched: { type_id: number; type_name: string; quantity: number }[];
  missing: { type_id: number; type_name: string; quantity: number }[];
  extra: { type_id: number; type_name: string; quantity: number }[];
}

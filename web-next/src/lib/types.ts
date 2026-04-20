// Minimal shape mirrors of the realms FastAPI responses.
// Kept loose — add fields as we need them on pages.

export interface EntitySummary {
  id: number;
  name: string;
  entity_type: string | null;
  alignment: string | null;
  realm: string | null;
  consensus_confidence: number;
  description?: string | null;
  cultural_associations?: string[];
  geographical_associations?: string[];
  powers?: string[];
  domains?: string[];
  first_documented_year?: number | null;
  review_status?: string;
}

export interface RelationshipRef {
  entity_id: number;
  entity_name: string | null;
  relationship_type: string;
  description: string | null;
  confidence: number;
  sources: number[];
  direction: 'in' | 'out';
}

export interface SourceRef {
  id: number;
  source_name: string;
  source_type: string | null;
  authors?: Array<{ name?: string } | string> | null;
  publication_year?: number | null;
  credibility_score?: number | null;
}

export interface ExtractionDetail {
  ingested_entity_id: number;
  extraction_method?: string;
  llm_model?: string;
  llm_temperature?: number;
  raw_quote?: string | null;
  confidence: number;
}

export interface EntityDetail extends EntitySummary {
  alternate_names: Record<string, string[]>;
  relationships: Record<string, RelationshipRef[]>;
  plant_connections: unknown[];
  sources: SourceRef[];
  extraction_details: ExtractionDetail[];
  evidence_period_start?: number | null;
  evidence_period_end?: number | null;
  historical_notes?: string | null;
  external_ids?: Record<string, string>;
  created_at?: string;
  updated_at?: string;
}

export interface CorroborationSource {
  id: number;
  source_name: string;
  url: string | null;
  doi: string | null;
  authors: unknown;
  publication_year: number | null;
  journal_or_venue: string | null;
  peer_reviewed: boolean | null;
  credibility_score: number | null;
  ingestion_status: string;
}

export interface Corroboration {
  entity_id: number;
  name: string;
  tier: 'tier_0' | 'tier_1' | 'tier_2' | 'tier_3';
  distinct_source_types: string[];
  sources_by_type: Record<string, CorroborationSource[]>;
  n_sources: number;
}

export interface Tradition {
  id: number;
  name: string;
  tradition_type?: string | null;
  region?: string | null;
  countries?: string[];
  description?: string | null;
  language_family?: string | null;
}

export interface Region {
  id: number;
  name: string;
  region_type?: string | null;
  center_latitude?: number | null;
  center_longitude?: number | null;
  countries?: string[];
}

"""
Pydantic schemas for API requests and responses
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# Base response model
class BaseResponse(BaseModel):
    data: Any
    meta: Dict[str, Any] = Field(default_factory=dict)

# Pagination model
class Pagination(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int

# Entity schemas
class EntitySummary(BaseModel):
    id: int
    name: str
    entity_type: Optional[str] = None
    alignment: Optional[str] = None
    realm: Optional[str] = None
    hierarchy_level: Optional[int] = None
    hierarchy_name: Optional[str] = None
    powers: List[str] = []
    domains: List[str] = []
    consensus_confidence: float
    cultural_associations: List[str] = []
    geographical_associations: List[str] = []

class EntityDetail(EntitySummary):
    description: Optional[str] = None
    alternate_names: Dict[str, List[str]] = {}
    relationships: Dict[str, List[Dict[str, Any]]] = {}
    plant_connections: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    extraction_details: List[Dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime

# Entity Class schemas
class EntityClassResponse(BaseModel):
    id: int
    name: str
    category_id: int
    description: Optional[str] = None
    core_powers: List[str] = []
    associated_plants: List[str] = []
    hierarchy_level: Optional[int] = None
    hierarchy_name: Optional[str] = None
    confidence_score: float

class EntityClassDetail(EntityClassResponse):
    entities: List[EntitySummary] = []
    provenance_sources: List[Dict[str, Any]] = []

# Hierarchy schemas
class HierarchyNode(BaseModel):
    id: int
    name: str
    type: str  # 'category', 'class', 'entity'
    entity_count: int = 0
    children: List['HierarchyNode'] = []
    meta: Dict[str, Any] = {}

HierarchyNode.model_rebuild()

class HierarchyTree(BaseModel):
    name: str
    children: List[HierarchyNode]

class HierarchyFlatItem(BaseModel):
    id: int
    name: str
    level: int
    path: List[str]
    entity_count: int
    confidence: float

class HierarchyFlat(BaseModel):
    data: List[HierarchyFlatItem]

# Relationship schemas
class RelationshipResponse(BaseModel):
    id: int
    source_entity_id: int
    target_entity_id: int
    relationship_type: str
    description: Optional[str] = None
    strength: Optional[str] = None
    confidence: float
    cultural_context: List[str] = []
    historical_period: List[str] = []

class RelationshipDetail(RelationshipResponse):
    source_entity: EntitySummary
    target_entity: EntitySummary
    provenance_sources: List[Dict[str, Any]] = []
    extraction_details: List[Dict[str, Any]] = []

# Culture schemas
class CultureResponse(BaseModel):
    id: int
    name: str
    language_family: Optional[str] = None
    region: Optional[str] = None
    countries: List[str] = []
    description: Optional[str] = None
    tradition_type: Optional[str] = None
    primary_plants: List[str] = []

class CultureDetail(CultureResponse):
    entities: List[EntitySummary] = []
    entity_pantheon: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []

# Region schemas
class RegionResponse(BaseModel):
    id: int
    name: str
    region_type: Optional[str] = None
    countries: List[str] = []
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    boundary_geojson: Optional[Dict[str, Any]] = None
    cultural_overlap: List[str] = []
    endemic_entities: List[str] = []
    shared_entities: List[str] = []

class RegionDetail(RegionResponse):
    entities: List[EntitySummary] = []
    sources: List[Dict[str, Any]] = []

# Source schemas
class SourceResponse(BaseModel):
    id: int
    source_type: str
    source_name: str
    authors: List[Dict[str, str]] = []
    publication_year: Optional[int] = None
    journal_or_venue: Optional[str] = None
    volume_issue: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None
    url: Optional[str] = None
    access_date: Optional[datetime] = None
    retrieval_method: Optional[str] = None
    language: str = 'en'
    original_language: Optional[str] = None
    translation_info: Optional[Dict[str, Any]] = None
    credibility_score: float
    peer_reviewed: bool = False
    citation_count: int = 0
    altmetrics: Optional[Dict[str, Any]] = None
    ingestion_status: str
    ingested_at: datetime
    processed_at: Optional[datetime] = None
    error_log: Optional[str] = None
    raw_content_hash: Optional[str] = None
    storage_path: Optional[str] = None
    access_restrictions: Optional[str] = None
    ethical_considerations: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class SourceDetail(SourceResponse):
    ingested_entities: List[Dict[str, Any]] = []
    extraction_statistics: Dict[str, Any] = {}

# Extraction schemas
class ExtractionResponse(BaseModel):
    id: int
    source_id: int
    extraction_method: str
    llm_model_used: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_prompt_version: Optional[str] = None
    raw_extracted_data: Dict[str, Any]
    normalized_data: Dict[str, Any]
    entity_name_raw: str
    entity_name_normalized: str
    extraction_confidence: float
    extraction_context: Optional[str] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    quote_context: Optional[str] = None
    status: str
    reviewer_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

# Stats schema
class StatsResponse(BaseModel):
    total_entities: int
    by_type: Dict[str, int]
    by_realm: Dict[str, int]
    by_alignment: Dict[str, int]
    by_culture: Dict[str, int]
    avg_confidence: float
    sources_processed: int
    total_extractions: int
    last_updated: datetime
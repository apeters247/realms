# REALMS Data Model

## Core Philosophy: Provenance-First Design

Every entity record must preserve complete source lineage with confidence scoring.
No data enters the system without traceable provenance.

## PostgreSQL Schema Details

### 1. IngestionSource Table
Tracks every document/source with maximum detail

```sql
CREATE TABLE ingestion_sources (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL, -- academic, internet, book, oral, ethnographic
    source_name VARCHAR(500) NOT NULL, -- Full title or name
    authors JSONB, -- Array of author objects: [{"name": "...", "affiliation": "..."}]
    publication_year INTEGER,
    journal_or_venue VARCHAR(200),
    volume_issue VARCHAR(100),
    pages VARCHAR(50),
    doi VARCHAR(100),
    isbn VARCHAR(20),
    url TEXT,
    access_date DATE, -- When we accessed it
    retrieval_method VARCHAR(100), -- API, manual entry, OCR, web scrape
    language VARCHAR(10) DEFAULT 'en',
    original_language VARCHAR(10),
    translation_info JSONB, -- Details if translated
    credibility_score FLOAT CHECK (credibility_score >= 0 AND credibility_score <= 1),
    peer_reviewed BOOLEAN,
    citation_count INTEGER,
    altmetrics JSONB, -- Alternative metrics if available
    ingestion_status VARCHAR(20) DEFAULT 'pending', -- pending, processing, completed, failed
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    error_log TEXT, -- If processing failed
    raw_content_hash VARCHAR(64), -- SHA256 of original for integrity
    storage_path VARCHAR(500), -- Where we stored the original
    access_restrictions VARCHAR(100), -- Copyright, paywall, etc.
    ethical_considerations TEXT, -- Any special handling notes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for provenance queries
CREATE INDEX idx_ingestion_sources_type ON ingestion_sources(source_type);
CREATE INDEX idx_ingestion_sources_year ON ingestion_sources(publication_year);
CREATE INDEX idx_ingestion_sources_doi ON ingestion_sources(doi);
CREATE INDEX idx_ingestion_sources_status ON ingestion_sources(ingestion_status);
```

### 2. IngestedEntity Table
Raw extraction output before normalization

```sql
CREATE TABLE ingested_entities (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES ingestion_sources(id) ON DELETE CASCADE,
    extraction_method VARCHAR(50), -- llm_prompt_v1, regex, manual
    llm_model_used VARCHAR(100), -- Which model did extraction
    llm_temperature FLOAT,
    llm_prompt_version VARCHAR(20), -- For reproducibility
    raw_extracted_data JSONB, -- Exactly what LLM returned
    normalized_data JSONB, -- After initial cleanup
    entity_name_raw VARCHAR(500), -- As found in source
    entity_name_normalized VARCHAR(500), -- Standardized form
    extraction_confidence FLOAT CHECK (extraction_confidence >= 0 AND extraction_confidence <= 1),
    extraction_context TEXT, -- Surrounding text where entity was found
    page_number INTEGER, -- If applicable
    section_title VARCHAR(200), -- Chapter/section heading
    quote_context TEXT, -- Direct quote containing entity mention
    status VARCHAR(20) DEFAULT 'raw', -- raw, normalized, confirmed, rejected
    reviewer_notes TEXT, -- For human review
    reviewed_by VARCHAR(100), -- Username if reviewed
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for extraction tracking
CREATE INDEX idx_ingested_entities_source ON ingested_entities(source_id);
CREATE INDEX idx_ingested_entities_status ON ingested_entities(status);
CREATE INDEX idx_ingested_entities_name ON ingested_entities(entity_name_normalized);
CREATE INDEX idx_ingested_entities_confidence ON ingested_entities(extraction_confidence);
```

### 3. Entity Hierarchy Tables

#### EntityCategory (Top-level taxonomy)
```sql
CREATE TABLE entity_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE, -- angelic, plant_spirit, animal_ally, ancestor, deity, demonic, nature_spirit, human_specialist
    description TEXT,
    parent_id INTEGER REFERENCES entity_categories(id), -- For subcategories
    icon_emoji VARCHAR(10), -- For UI display
    provenance_note TEXT, -- How this category was defined
    sources JSONB, -- Array of source IDs that informed this category
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### EntityClass (Specific types within categories)
```sql
CREATE TABLE entity_classes (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES entity_categories(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL, -- Primary name (indigenous if known)
    alternate_names JSONB, -- {"Spanish": ["dueño"], "Shipibo": ["ibo"], "English": ["plant spirit"]}
    description TEXT,
    core_powers JSONB, -- ["healing", "protection", "divination"]
    associated_plants JSONB, -- Plant entities this traditionally teaches
    cultural_origin JSONB, -- Which cultures primarily recognize this class
    hierarchy_level INTEGER, -- 1-10 within category
    hierarchy_name VARCHAR(100), -- e.g., "archangel", "master", "lesser spirit"
    provenance_sources JSONB, -- Source IDs that define this class
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_entity_classes_category ON entity_classes(category_id);
CREATE INDEX idx_entity_classes_name ON entity_classes(name);
```

#### Entity (Individual documented instances)
```sql
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    entity_class_id INTEGER REFERENCES entity_classes(id) ON DELETE SET NULL,
    name VARCHAR(200) NOT NULL,
    entity_type VARCHAR(50), -- angelic, plant_spirit, animal_ally, ancestor, deity, nature_spirit
    alignment VARCHAR(20), -- beneficial, neutral, malevolent, protective
    realm VARCHAR(100), -- earth, sky, underworld, water, forest, hyperspace
    hierarchy_level INTEGER, -- Overall hierarchy position
    hierarchy_name VARCHAR(100),
    powers JSONB, -- List of specific capabilities
    domains JSONB, -- Spheres of influence (fertility, death, war, etc.)
    associated_animals JSONB, -- Shapeshift forms or companions
    plant_teachers JSONB, -- Plants this entity teaches about
    geographical_associations JSONB, -- Regions where commonly encountered
    cultural_associations JSONB, -- Cultures that document this entity
    provenance_sources JSONB, -- Direct sources mentioning THIS specific entity
    extraction_instances JSONB, -- Array of ingested_entity_ids that contributed
    consensus_confidence FLOAT CHECK (consensus_confidence >= 0 AND consensus_confidence <= 1),
    conflict_notes TEXT, -- When sources disagree about this entity
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_entities_class ON entities(entity_class_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_alignment ON entities(alignment);
CREATE INDEX idx_entities_realm ON entities(realm);
CREATE INDEX idx_entities_confidence ON entities(consensus_confidence);
```

### 4. Relationship Tracking with Provenance

#### EntityRelationship Table
```sql
CREATE TABLE entity_relationships (
    id SERIAL PRIMARY KEY,
    source_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL, -- parent_of, allied_with, teacher_of, enemy_of, manifests_as
    description TEXT,
    strength VARCHAR(20), -- strong, moderate, weak, speculative
    provenance_sources JSONB, -- Sources documenting THIS relationship
    extraction_confidence FLOAT CHECK (extraction_confidence >= 0 AND extraction_confidence <= 1),
    cultural_context JSONB, -- Which cultures describe this relationship
    historical_period JSONB, -- Time period when relationship was described
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_entity_relationships_source ON entity_relationships(source_entity_id);
CREATE INDEX idx_entity_relationships_target ON entity_relationships(target_entity_id);
CREATE INDEX idx_entity_relationships_type ON entity_relationships(relationship_type);
```

#### PlantSpiritConnection Table (Bridge to EstimaBio compounds)
```sql
CREATE TABLE plant_spirit_connections (
    id SERIAL PRIMARY KEY,
    compound_id VARCHAR(36) REFERENCES compounds(id) ON DELETE SET NULL, -- Link to EstimaBio
    entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL, -- teacher, ally, owner, manifestation, guardian
    preparation_method VARCHAR(100), -- How encountered: ayahuasca, tobacco, diet, smoke
    context_description TEXT, -- Situation where connection was made
    cultural_association JSONB, -- Which cultures document this connection
    geographical_association JSONB, -- Where this connection is found
    provenance_sources JSONB, -- Sources documenting THIS connection
    extraction_confidence FLOAT CHECK (extraction_confidence >= 0 AND extraction_confidence <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_plant_spirit_connections_compound ON plant_spirit_connections(compound_id);
CREATE INDEX idx_plant_spirit_connections_entity ON plant_spirit_connections(entity_id);
```

### 5. Cultural and Geographic Context

#### Culture Table
```sql
CREATE TABLE cultures (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL, -- Shipibo-Konibo, Yanomami, Yoruba, etc.
    language_family VARCHAR(100), -- Panoan, Yanomaman, Niger-Congo, etc.
    region VARCHAR(100), -- Upper Amazon, West Africa, Siberia, etc.
    countries JSONB, -- Array of country codes
    description TEXT,
    tradition_type VARCHAR(50), -- vegetalismo, shamanism, orisha_worship, etc.
    primary_plants JSONB, -- Main teacher plants in this tradition
    entity_pantheon JSONB, -- Documented entity hierarchy for this culture
    sources JSONB, -- Source IDs defining this culture
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### GeographicRegion Table
```sql
CREATE TABLE geographic_regions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL, -- Amazon Basin, Andes, Sahara, etc.
    region_type VARCHAR(50), -- tropical, arctic, desert, mountain, etc.
    countries JSONB,
    center_latitude FLOAT,
    center_longitude FLOAT,
    boundary_geojson JSONB, -- For map display
    cultural_overlap JSONB, -- Other regions sharing traditions
    endemic_entities JSONB, -- Entities found ONLY here
    shared_entities JSONB, -- Entities also found elsewhere
    sources JSONB, -- Source IDs defining this region's traditions
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Provenance Tracking Principles

### 1. Three-Layer Provenance
Every fact has:
- **Source Layer:** Which document(s) state this
- **Extraction Layer:** How we got it from the document (LLM prompt, manual, etc.)  
- **Consensus Layer:** How multiple sources agree/disagree

### 2. Confidence Propagation
- Extraction confidence (0-1) from LLM/manual
- Source credibility (0-1) based on peer review, author expertise
- Cross-source consensus boosts confidence
- Conflicting sources reduce confidence with notes

### 3. Immutable Source Records
- Original sources never modified
- Extractions stored as-is with method/version
- Normalization creates new records, doesn't overwrite
- All changes tracked with timestamps

### 4. Attribution Requirements
When displaying any entity information:
- Show top 3 sources with confidence scores
- Show extraction method and model used
- Show consensus level and any conflicts
- Provide links to original sources when available

## Indexing Strategy for Provenance Queries

```sql
-- Find all sources mentioning a specific entity
CREATE INDEX idx_provenance_entity_sources ON entities USING GIN (provenance_sources);

-- Find extraction instances for fact-checking
CREATE INDEX idx_provenance_extraction ON ingested_entities USING GIN (extraction_instances);

-- Cultural geographic queries
CREATE INDEX idx_provenance_culture ON cultures USING GIN (countries);
CREATE INDEX idx_provenance_region ON geographic_regions USING GIN (countries);

-- Temporal analysis
CREATE INDEX idx_provenance_time ON ingestion_sources(publication_year);
CREATE INDEX idx_provenance_processed ON ingestion_sources(processed_at);
```

## Data Quality Controls

### Validation Constraints
- All confidence scores between 0 and 1
- Dates must be reasonable (no future dates beyond 1 year)
- Entity names cannot be empty
- Relationships cannot be self-referential
- Hierarchy levels must be positive integers

### Audit Triggers
```sql
-- Track all changes to entity records for provenance
CREATE TRIGGER track_entity_changes
AFTER UPDATE ON entities
FOR EACH ROW
EXECUTE FUNCTION log_entity_provenance_change();

CREATE OR REPLACE FUNCTION log_entity_provenance_change()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO entity_provenance_log (
        entity_id,
        changed_fields,
        old_values,
        new_values,
        changed_by,
        change_reason
    ) VALUES (
        OLD.id,
        /* Calculate changed fields */,
        row_to_json(OLD),
        row_to_json(NEW),
        current_user,
        'Automatic provenance tracking'
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

## Sample Provenance Query

```sql
-- Get full provenance for an entity claim
SELECT 
    e.name as entity_name,
    ec.name as entity_class,
    array_agg(DISTINCT s.source_name) as sources,
    array_agg(DISTINCT ie.extraction_method) as methods,
    avg(e.consensus_confidence) as confidence,
    array_agg(DISTINCT ie.status) as extraction_status
FROM entities e
JOIN entity_classes ec ON e.entity_class_id = ec.id
JOIN ingested_entities ie ON ie.id = ANY(e.extraction_instances)
JOIN ingestion_sources s ON ie.source_id = s.id
WHERE e.id = 123
GROUP BY e.name, ec.name;
```
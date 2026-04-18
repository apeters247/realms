# REALMS API Specification

## Base URL
```
https://api.realms.org/api/v1
```

All endpoints return JSON unless otherwise noted.
All timestamps in ISO 8601 format with timezone.
Successful responses: 200 OK (GET/PUT) or 201 Created (POST)
Error responses: Standard HTTP error codes with JSON error details

## Authentication
**NOTE:** This is a read-only public service. No authentication required for any endpoint.
Rate limiting may apply: 60 requests/minute per IP.

## Pagination
List endpoints support pagination:
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 50, max: 100)
Response includes: `total`, `page`, `per_page`, `total_pages`

## Filtering & Search
Most list endpoints support:
- `q`: General search query (searches name, description, etc.)
- Specific field filters: `entity_type=plant_spirit`, `realm=forest`
- Range filters: `confidence_min=0.8`, `hierarchy_level_max=5`
- Sorting: `sort=-consensus_confidence,name` (prefix `-` for descending)

## Response Format
Successful responses:
```json
{
  "data": /* payload */,
  "meta": {
    "timestamp": "2026-04-18T10:30:00Z",
    "version": "1.0.0"
  }
}
```

Paginated responses:
```json
{
  "data": [...],
  "pagination": {
    "total": 1250,
    "page": 1,
    "per_page": 50,
    "total_pages": 25
  },
  "meta": {/* same as above */}
}
```

Error responses:
```json
{
  "error": {
    "code": "ENTITY_NOT_FOUND",
    "message": "Entity with ID 99999 not found",
    "details": {/* optional additional info */}
  }
}
```

---

## Endpoints

### Entities

#### List Entities
```
GET /entities
```

Filters:
- `entity_type`: angelic, plant_spirit, animal_ally, ancestor, deity, nature_spirit
- `alignment`: beneficial, neutral, malevolent
- `realm`: earth, sky, underworld, water, forest, hyperspace
- `hierarchy_level_min`, `hierarchy_level_max`
- `confidence_min`, `confidence_max`
- `culture_id`: Filter by culture
- `region_id`: Filter by geographic region
- `power`: Specific power name
- `domain`: Specific domain of influence
- `q`: General search (name, description, alternate names)

Response:
```json
{
  "data": [
    {
      "id": 123,
      "name": "Xapiripë",
      "entity_type": "animal_ally",
      "alignment": "beneficial",
      "realm": "forest",
      "hierarchy_level": 8,
      "hierarchy_name": "shamanic spirit",
      "powers": ["healing", "protection", "divination", "plant_teaching"],
      "domains": ["forest_health", "spirit_world_access"],
      "consensus_confidence": 0.95,
      "extraction_instances": [456, 789],
      "provenance_sources": [12, 34, 56],
      "cultural_associations": ["Yanomami"],
      "geographical_associations": ["Amazon Basin"],
      "alternate_names": {
        "Yanomami": ["xapiri", "xapiripë"],
        "English": ["spirits of the forest"]
      },
      "created_at": "2026-04-15T14:22:00Z",
      "updated_at": "2026-04-16T09:15:00Z"
    }
  ],
  "pagination": {/* ... */},
  "meta": {/* ... */}
}
```

#### Get Entity Detail
```
GET /entities/{id}
```

Response includes expanded relationships and provenance:
```json
{
  "data": {
    "id": 123,
    "name": "Xapiripë",
    /* ... basic fields from list ... */
    "description": "The xapiripë are the animal ancestor spirits of the Yanomami shamans...",
    "relationships": {
      "allied_with": [
        {
          "entity_id": 456,
          "entity_name": "Chullachaqui",
          "relationship_type": "allied_with",
          "description": "Often work together in healing ceremonies",
          "confidence": 0.8,
          "sources": [12, 34],
          "cultural_context": "Yanomami shamanic practice"
        }
      ],
      "teacher_of": [
        {
          "entity_id": 789,
          "entity_name": "Banisteriopsis caapi",
          "relationship_type": "teacher_of",
          "description": "Teaches shamans about the ayahuasca vine",
          "confidence": 0.9,
          "sources": [56],
          "cultural_context": "Documented in Viveiros de Castro's work"
        }
      ],
      "manifests_as": [
        {
          "form_description": "Tiny humanoid figures that dance on mirrors",
          "confidence": 0.85,
          "sources": [12, 34, 56, 78]
        }
      ]
    },
    "plant_connections": [
      {
        "compound_id": "a1b2c3d4-e5f6-7890-g1h2-i3j4k5l6m7n8",
        "compound_name": "Banisteriopsis caapi",
        "relationship_type": "teacher_of",
        "preparation": "ayahuasca brew",
        "confidence": 0.9,
        "sources": [56],
        "cultural_context": "Yanomami and Shipibo traditions"
      }
    ],
    "sources": [
      {
        "id": 12,
        "source_name": "The Falling Sky: Words of a Yanomami Shaman",
        "source_type": "book",
        "authors": [{"name": "Davi Kopenawa", "affiliation": "Yanomami shaman"}],
        "publication_year": 2013,
        "credibility_score": 0.95,
        "extraction_confidence": 0.9
      }
      /* ... more sources ... */
    ],
    "extraction_details": [
      {
        "ingested_entity_id": 456,
        "extraction_method": "llm_prompt_v2",
        "llm_model": "deepseek-chat",
        "llm_temperature": 0.1,
        "raw_quote": "We Yanomami learn with the great spirits, the xapiripë...",
        "confidence": 0.88
      }
      /* ... more extractions ... */
    ]
  },
  "meta": {/* ... */}
}
```

### Entity Classes

#### List Entity Classes
```
GET /entity-classes
```

Filters:
- `category_id`: Filter by top-level category
- `hierarchy_level_min`, `hierarchy_level_max`
- `confidence_min`
- `q`: Search name/description

Response includes class definition and member entities count.

#### Get Entity Class Detail
```
GET /entity-classes/{id}
```

Response includes:
- Class definition
- List of entities in this class (paginated)
- Hierarchy position within category
- Associated cultures
- Core powers and domains
- Provenance sources

### Hierarchy Endpoints

#### Get Full Hierarchy Tree
```
GET /hierarchy/tree
```

Returns nested JSON suitable for D3.js tree visualization:
```json
{
  "data": {
    "name": "root",
    "children": [
      {
        "name": "PRIMORDIAL DIVINITIES",
        "children": [
          {
            "name": "Olodumare",
            "entities": [/* array of entity objects */],
            "meta": {/* confidence, sources, etc. */}
          }
          /* ... more entities in this class ... */
        ]
      },
      {
        "name": "PLANT TEACHERS / SPIRITS",
        "children": [
          {
            "name": "Chullachaqui",
            "entities": [...]
          }
          /* ... more classes ... */
        ]
      }
      /* ... more top-level categories ... */
    ]
  },
  "meta": {/* ... */}
}
```

#### Get Hierarchy as Flat List with Levels
```
GET /hierarchy/flat
```

Returns:
```json
{
  "data": [
    {
      "id": 1,
      "name": "Olodumare",
      "level": 1,
      "path": ["PRIMORDIAL DIVINITIES", "Olodumare"],
      "entity_count": 1,
      "confidence": 0.9
    }
    /* ... flattened hierarchy ... */
  ],
  "meta": {/* ... */}
}
```

### Relationships

#### List Relationships
```
GET /relationships
```

Filters:
- `relationship_type`: parent_of, allied_with, teacher_of, etc.
- `source_entity_id`
- `target_entity_id`
- `confidence_min`
- `cultural_context`
- `historical_period`

#### Get Relationship Detail
```
GET /relationships/{id}
```

Returns full provenance for the relationship.

### Cultures

#### List Cultures
```
GET /cultures
```

Filters:
- `region`: Upper Amazon, West Africa, etc.
- `tradition_type`: vegetalismo, shamanism, etc.
- `language_family`
- `q`: Search name/description

#### Get Culture Detail
```
GET /cultures/{id}
```

Returns:
- Culture definition
- List of entities documented by this culture (paginated)
- Associated geographic regions
- Primary plants
- Entity pantheon hierarchy
- Provenance sources

### Geographic Regions

#### List Regions
```
GET /regions
```

Filters:
- `region_type`: tropical, arctic, etc.
- `q`: Search name/description

#### Get Region Detail
```
GET /regions/{id}
```

Returns:
- Region definition
- List of entities associated with this region
- Cultural overlap with other regions
- Endemic vs shared entities
- Map boundary data (GeoJSON)

### Provenance & Sources

#### List Sources
```
GET /sources
```

Filters:
- `source_type`: academic, internet, book, etc.
- `publication_year_min`, `publication_year_max`
- `peer_reviewed`: true/false
- `credibility_min`
- `ingestion_status`: pending, processing, completed, failed
- `q`: Search title/authors/doi

#### Get Source Detail
```
GET /sources/{id}
```

Returns:
- Complete source metadata
- List of ingested entities from this source
- Extraction statistics
- Access information (when available)

#### Get Extraction Detail
```
GET /extractions/{id}
```

Returns:
- Raw LLM output
- Normalized data
- Extraction method and parameters
- Review status and notes
- Links to final entity records

### Search Endpoints

#### Global Search
```
GET /search?q=ayahuasca+spirits
```

Searches across entities, classes, cultures, sources.
Returns categorized results:
```json
{
  "data": {
    "entities": [...],
    "entity_classes": [...],
    "cultures": [...],
    "sources": [...]
  },
  "meta": {/* ... */}
}
```

#### Advanced Search (POST for complex queries)
```
POST /search/advanced
```

Body:
```json
{
  "filters": {
    "entity_type": "plant_spirit",
    "realm": "forest",
    "cultures": ["Yanomami", "Shipibo"],
    "confidence_min": 0.8
  },
  "sort": "-consensus_confidence",
  "page": 1,
  "per_page": 20
}
```

### Statistics & Reports

#### Get Statistics
```
GET /stats
```

Returns:
```json
{
  "data": {
    "total_entities": 1250,
    "by_type": {
      "plant_spirit": 320,
      "animal_ally": 280,
      /* ... */ 
    },
    "by_realm": {
      "forest": 410,
      "sky": 290,
      /* ... */
    },
    "by_alignment": {
      "beneficial": 650,
      "neutral": 450,
      "malevolent": 150
    },
    "by_culture": {
      "Yanomami": 180,
      "Shipibo": 150,
      /* ... */
    },
    "avg_confidence": 0.82,
    "sources_processed": 342,
    "total_extractions": 1250,
    "last_updated": "2026-04-17T10:30:00Z"
  },
  "meta": {/* ... */}
}
```

#### Export Endpoints (Read-only data dumps)
```
GET /export/entities.csv
GET /export/entities.json
GET /export/relationships.csv
GET /export/cultures.json
```
Returns CSV or JSON dump of public data (no PII).

---

## Rate Limiting
- 60 requests per minute per IP
- Burst allowance: 120 requests
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- 429 Too Many Requests when exceeded

## CORS
Publicly accessible: `Access-Control-Allow-Origin: *`

## Versioning
Current version: v1
Deprecation notice: 6 months minimum for breaking changes

## Error Codes
- 400: Bad Request (invalid parameters)
- 401: Unused (service is public)
- 403: Forbidden (attempt to write to read-only service)
- 404: Not Found
- 409: Conflict (should not occur in read-only)
- 422: Unprocessable Entity (validation failure)
- 429: Too Many Requests
- 500: Internal Server Error
- 503: Service Unavailable

## Example Usage

### Get all beneficial plant spirits from Amazon with high confidence
```
GET /entities?entity_type=plant_spirit&alignment=beneficial&realm=forest&confidence_min=0.85
```

### Get hierarchy for teaching spirits
```
GET /hierarchy/tree?q=teacher
```

### Get Yanomami entity pantheon
```
GET /cultures?name=Yanomami  // Get culture ID first
GET /cultures/{id}          // Then get detail with entity list
```

### Research provenance of a specific claim
```
GET /entities/123          // Get entity with full provenance
GET /sources/34            // Check one of the sources
GET /extractions/456       // See how it was extracted
```
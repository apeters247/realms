# REALMS Architecture

## Overview

REALMS is designed as a read-only, public-facing service that extends the existing EstimaBio infrastructure while maintaining clear separation of concerns. The architecture follows a modular, service-oriented design with explicit data flow layers.

## Architectural Principles

1. **Provenance-First**: Every data element preserves complete source lineage
2. **Separation of Concerns**: Distinct layers for ingestion, storage, API, and presentation
3. **Extensibility**: Easy to add new entity types, relationship types, and data sources
4. **Read-Only Optimization**: Optimized for fast reads, no write concerns after ingestion
5. **Leverage Existing Infrastructure**: Reuses PostgreSQL, Neo4j, and Docker base from EstimaBio
6. **Fault Tolerance**: Designed to handle partial failures in ingestion pipeline gracefully

## System Components

### 1. Data Ingestion Layer
Responsible for discovering, extracting, and normalizing source material into the database.

**Components:**
- **Source Discovery Service**: Crawls academic databases, websites, and document repositories
- **Extraction Workers**: LLM-powered and rule-based extractors that process source documents
- **Normalization Service**: Converts raw extractions to standardized entity records
- **Provenance Tracker**: Maintains detailed source lineage and confidence scoring
- **Review Queue**: Holds low-confidence extractions for potential human review (though system is read-only, we flag for internal quality)

### 2. Storage Layer
Persistent storage using extended EstimaBio PostgreSQL and Neo4j instances.

**PostgreSQL Extension:**
- Contains all REALMS-specific tables (see DATA_MODEL.md)
- Optimized for complex queries and provenance tracking
- Uses connection pooling shared with EstimaBio services

**Neo4j Knowledge Graph:**
- Stores entity relationships for graph traversal and visualization
- Synchronized with PostgreSQL via change triggers or periodic sync
- Optimized for relationship-heavy queries

### 3. API Layer
FastAPI service providing read-only endpoints for all data.

**Features:**
- Automatic OpenAPI/Swagger documentation
- Request validation and response serialization
- CORS enabled for public access
- Rate limiting and basic security headers
- Health check and metrics endpoints
- Pagination, filtering, and sorting on all list endpoints
- Full-text search capabilities

### 4. Presentation Layer
Static web application served via the API or separate static hosting.

**Components:**
- React/Vue.js or vanilla JS frontend (to be decided)
- D3.js for hierarchy visualizations
- Cytoscape.js for knowledge graph exploration
- Leaflet.js for geographic mapping
- Responsive design for desktop and mobile

### 5. Monitoring & Maintenance
- Health checks for all services
- Logging pipeline (to EstimaBio's log infrastructure)
- Metrics collection (Prometheus-compatible)
- Backup procedures (leverages existing EstimaBio backup)

## Data Flow Detailed

### Ingestion Pipeline
```
Source Acquisition → 
  [Web Scrape / API Fetch / Manual Upload] →
Document Storage (immutable) →
  [Hash verified, stored in data/raw/] →
Preprocessing →
  [Text extraction, OCR if needed, language detection] →
Chunking →
  [Semantic or fixed-size chunks for LLM processing] →
Extraction →
  [LLM prompt or regex rules → Raw JSON output] →
Normalization →
  [Confidence scoring, deduplication, standardization] →
Provenance Linking →
  [Connect to sources, calculate consensus confidence] →
Database Write →
  [PostgreSQL tables + Neo4j sync] →
Index Updates →
  [Refresh search indexes and materialized views] →
```

### Query Flow
```
HTTP Request → 
  [API Gateway (FastAPI)] →
Request Validation & Parsing →
  [Query builder with filters/pagination] →
Database Query →
  [PostgreSQL with JOINs for related data] →
Result Transformation →
  [Add provenance summary, format for client] →
HTTP Response →
  [JSON with data, meta, pagination info] →
```

## Technology Choices Justification

### Why Extend EstimaBio PostgreSQL?
- Reuses existing connection pooling, backup, and monitoring
- ACID transactions ensure data integrity for provenance tracking
- JSONB columns perfect for flexible, provenance-rich metadata
- Familiar tooling and expertise already present
- No need to manage separate database cluster

### Why Use Neo4j for Relationships?
- Graph traversals (e.g., "show all entities allied with X") are natural in graph DB
- Visualization tools (Cytoscape.js, Neo4j Bloom) work natively
- Handles dense relationship networks better than relational DB for this use case
- Already running in EstimaBio infrastructure (we leverage existing instance)

### Why FastAPI?
- High performance (async capabilities)
- Automatic OpenAPI documentation
- Pydantic models for data validation
- Easy to extend and maintain
- Matches existing EstimaBio API technology

### Why Separate Service?
- Independent scaling: ingestion bursts don't affect API performance
- Clear boundaries: read-only vs read-write concerns
- Deployment flexibility: can run on different hardware profiles
- Team separation: different teams can work on ingestion vs feature development
- Failure isolation: ingestion pipeline issues don't bring down public API

## Security Considerations (Read-Only Service)

### Network Security
- Runs in same Docker network as EstimaBio services
- No direct external database access (only via internal network)
- API exposed via existing reverse proxy or separate port

### Data Security
- No PII stored (all data is public domain or properly attributed)
- Immutable source storage prevents tampering
- Read-only database user for API connections
- Regular security scanning of dependencies

### API Security
- Rate limiting to prevent abuse
- CORS headers controlled
- Input validation prevents injection attacks
- No authentication endpoints (service is public)
- Security headers: X-Content-Type-Options, X-Frame-Options, etc.

## Scalability Considerations

### Horizontal Scaling
- Ingestion workers can be scaled independently based on source volume
- API can be scaled behind load balancer for user traffic
- Neo4j supports clustering for read scaling (if needed later)

### Vertical Scaling
- PostgreSQL can utilize available RAM for caching
- Extraction workers benefit from CPU for LLM processing
- Storage scales with data volume (projected 100K-1M entities over time)

### Caching Strategy
- API response caching for frequent queries (Redis optional)
- Neo4j query caching for common traversals
- Browser caching for static assets
- CDN consideration for global audience

## Failure Modes & Mitigation

### Ingestion Pipeline Failures
- **Source unavailable**: Retry with exponential backoff, alert after N failures
- **LLM API failure**: Queue requests, fallback to rule-based extraction
- **Database connection failure**: Buffer extractions, retry with backoff
- **Processing errors**: Move to dead-letter queue for manual inspection

### Storage Failures
- **PostgreSQL unavailable**: Ingestion pauses, API serves cached/stale data if possible
- **Neo4j unavailable**: API falls back to PostgreSQL-only mode for relationship queries
- **Disk space**: Monitoring and alerts; ingestion stops before critical levels

### API Failures
- **Application crash**: Restart policy in Docker, health checks trigger alerts
- **Network issues**: Standard Docker networking resilience
- **Bad requests**: Return appropriate HTTP errors without crashing

## Data Model Evolution Strategy

### Versioning Approach
- Immutable source records never change
- Entity records can be updated with higher confidence extractions
- Schema changes via Alembic migrations (backward compatible where possible)
- Deprecation period for any breaking changes (though read-only reduces risk)

### Handling Conflicting Information
- Store all provenance with confidence scores
- Display multiple perspectives when sources disagree
- Flag entities with high conflict for special attention
- Allow users to see the underlying debate in source materials

## Integration Points with EstimaBio

### Database
- Shares PostgreSQL instance (different schemas or same schema with prefix)
- Connection pool configuration shared via environment
- Backup procedures unchanged (backs up entire database)

### Neo4j
- Shares existing Neo4j instance
- Uses same authentication and connection settings
- Leverages existing APOC plugins if needed

### Docker & Networking
- Part of same docker-compose.yml (separate service definition)
- Shares estimabio-network for inter-service communication
- Can reuse existing volumes for logs, data if appropriate

### Monitoring
- Shares Prometheus metrics endpoint if desired
- Logs go to same Docker logging drivers
- Health checks integrated into existing monitoring

### Development Environment
- Same docker-compose dev setup applies
- Shared code volumes (./tools, ./agents) if common utilities needed
- Can reuse existing pytest fixtures and testing patterns

## Future Extension Points

### 1. Advanced Analytics Layer
- Statistical analysis of entity distributions
- Network analysis of relationship graphs
- Temporal analysis of belief evolution

### 2. Community Contribution System
- While initially read-only, design allows for future contribution workflow
- Provenance tracking would extend to user submissions
- Moderation and approval processes

### 3. Multilingual Support
- Store original language extractions
- Provide translations via linked sources
- UI language selection

### 4. Temporal Dimensions
- Historical dating of entity beliefs
- Evolution tracking of beliefs over time
- Geographic spread animations

### 5. Cross-Database Linking
- Formal Wikidata integration
- Link to other knowledge graphs (WordNet, DBpedia, etc.)
- Authority control via VIAF or similar

## Diagram Overview (Textual)

```
[Source Documents] 
       ↓ (Discovery)
[Source Archive] ←───┐
       ↓              │
[Extraction Workers] │
       ↓              │
[Normalization]      │
       ↓              │
[PostgreSQL] ←───────┘
       ↓
[Neo4j Sync] → [Neo4j Graph]
       ↓
     [API Service]
       ↓
[Web Clients / API Consumers]
```

## Conclusion

This architecture provides a solid foundation for a read-only, provenance-rich spiritual entity knowledge base that leverages existing EstimaBio infrastructure while maintaining clear separation of concerns. The focus on provenance tracking ensures academic rigor, while the modular design allows for evolution and expansion as the project grows.
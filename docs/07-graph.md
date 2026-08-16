# REALMS Neo4j Graph

## Purpose

Neo4j mirrors the REALMS PostgreSQL data for graph-native queries and Cytoscape.js visualization. The sync runs every 30 seconds and is **unidirectional**: Postgres → Neo4j only. All writes go through the API to Postgres; Neo4j is a read replica specialized for graph traversal.

## Node Labels

| Label | Source Table | Key Property | Sync Strategy |
|-------|-------------|-------------|----------------|
| `Entity` | `entities` | `realms_id` (unique) | Full resync each pass |
| `EntityClass` | `entity_classes` | `realms_id` (unique) | Full resync each pass |
| `Culture` | `cultures` | `name` (unique) | Full resync each pass |
| `Region` | `geographic_regions` | `name` (unique) | Full resync each pass |

## Relationship Types

| Type | Source | Direction |
|------|--------|-----------|
| `INSTANCE_OF` | Entity → EntityClass | Entity belongs to class |
| `DOCUMENTED_BY` | Entity → Culture | Entity documented by culture |
| `FOUND_IN` | Entity → Region | Entity associated with region |
| Dynamic typed edges | Entity → Entity | Same as `entity_relationships.relationship_type`, uppercased (e.g. `PARENT_OF`, `SIBLING_OF`, `ALLIED_WITH`) |

## Sync Mechanism

### Code: `realms/sync/neo4j_sync.py` (315 lines)

```
run_forever()
  │
  ├── _install_signal_handlers()   # SIGTERM/SIGINT graceful shutdown
  │
  └── loop every 30s:
        run_once()
          │
          ├── _ensure_constraints()  # CREATE CONSTRAINT IF NOT EXISTS for each label
          │
          ├── _sync_entities()       # MERGE Entity nodes + link to Culture/Region/Class
          ├── _sync_classes()        # MERGE EntityClass nodes
          ├── _sync_cultures()       # MERGE Culture nodes
          ├── _sync_regions()        # MERGE Region nodes
          ├── _sync_relationships()  # Group by type, UNWIND MERGE edges
          │
          └── _delete_stale()        # DETACH DELETE nodes not in Postgres
```

### Key Details

- **Current strategy:** Full resync every pass (incremental via `updated_at` checkpoint table planned)
- **Batching:** Uses Cypher `UNWIND` for batch MERGE operations
- **Entity sync:** Also creates `DOCUMENTED_BY` → Culture and `FOUND_IN` → Region edges in the same Cypher query
- **Relationship sync:** Groups by type and creates dynamic relationship labels (`PARENT_OF`, `CO_OCCURS_WITH`, etc.)
- **Delete detection:** Queries `realms_id` from Neo4j, crosses against PostgreSQL `id` set, `DETACH DELETE`s stale nodes

### Constraints

```cypher
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.realms_id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:EntityClass) REQUIRE n.realms_id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Culture) REQUIRE n.realms_id IS UNIQUE
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Region) REQUIRE n.realms_id IS UNIQUE
```

## Cypher Query Examples

### Get entity with all relationships

```cypher
MATCH (a:Entity)-[r]->(b:Entity)
WHERE a.realms_id = 123 AND type(r) <> 'CO_OCCURS_WITH'
RETURN a, r, b
```

### High-confidence semantic relationships

```cypher
MATCH (a:Entity)-[r]->(b:Entity)
WHERE a.consensus_confidence > 0.85 AND type(r) <> 'CO_OCCURS_WITH'
RETURN a, r, b LIMIT 50
```

### All entities in a culture, with class

```cypher
MATCH (e:Entity)-[:DOCUMENTED_BY]->(c:Culture {name: 'Yoruba'})
MATCH (e)-[:INSTANCE_OF]->(cl:EntityClass)
RETURN e.name, cl.name
```

### Ego network (2-hop BFS)

```cypher
MATCH (center:Entity {realms_id: 123})
CALL {
  MATCH (center)-[r]-(neighbor:Entity)
  RETURN neighbor, r
  UNION
  MATCH (center)-[*2]-(hop2:Entity)
  RETURN hop2, NULL as r
}
RETURN DISTINCT neighbor, r
```

## API Integration

The Graph API endpoints (`/graph/` routes) use the FastAPI service directly against PostgreSQL for Cytoscape-formatted data, NOT Neo4j. Neo4j is available for:
- Manual exploration via Neo4j Browser (port 7474 if exposed)
- Future optimized graph traversal endpoints
- External graph analysis tools

## Node Properties

### Entity

```
realms_id, name, entity_type, alignment, realm,
hierarchy_level, hierarchy_name, consensus_confidence,
description, cultural_associations[], geographical_associations[]
```

### EntityClass

```
realms_id, name, hierarchy_level, hierarchy_name, description
```

### Culture

```
realms_id, name, region, tradition_type, language_family
```

### Region

```
realms_id, name, region_type, center_latitude, center_longitude
```

## Configuration

| Env Var | Default | Purpose |
|---------|---------|---------|
| `NEO4J_URI` | `bolt://neo4j:7687` | Neo4j connection |
| `NEO4J_USER` | `neo4j` | |
| `NEO4J_PASSWORD` | (required) | |
| `REALMS_SYNC_INTERVAL` | 30 | Seconds between sync passes |

## Running

```bash
docker compose exec realms-neo4j-sync python -m scripts.run_neo4j_sync
```

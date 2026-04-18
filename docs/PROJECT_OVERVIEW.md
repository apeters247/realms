# REALMS: Research Entity Archive for Light & Metaphysical Spirit Hierarchies

## Project Vision

REALMS is an open-access, read-only research platform for documenting, categorizing, and visualizing spiritual entities encountered in indigenous traditions worldwide, with special focus on those experienced through ayahuasca and other entheogenic practices.

## Core Mission

To create the most comprehensive knowledge base mapping:
- Spiritual entity hierarchies and relationships
- Geographic and cultural origins  
- Documented powers, domains, and characteristics
- Connections to plant teachers and indigenous knowledge systems
- Historical and contemporary accounts across traditions

## Scope

**Global Indigenous Traditions Covered:**
- **Amazonian:** Ayahuasca traditions (Shipibo, mestizo vegetalismo, Yanomami)
- **African:** Yoruba/Orisha, Vodun, Santeria, Candomblé
- **Siberian/Uralic:** Shamanic traditions (Nenets, Nganasan, Yakut)
- **Native American:** Various tribal traditions
- **Polynesian/Melanesian:** Austronesian beliefs (via Pulotu framework)
- **Global Entheogenic:** DMT entity encounters, machine elves, tryptamine experiences

## Key Features

1. **Entity Database:** Comprehensive catalog of spiritual beings with attributes
2. **Hierarchy Mapping:** Visual taxonomies showing relationships and power structures  
3. **Geographic Mapping:** Origins and cultural distribution maps
4. **Plant Connections:** Links to teacher plants and ethnobotanical knowledge
5. **Academic Literature Integration:** Systematic extraction from peer-reviewed sources
6. **Provenance Tracking:** Detailed source preservation with extraction confidence, context, and lineage
7. **Interactive Visualization:** D3.js hierarchies, Cytoscape.js knowledge graphs, Leaflet maps
8. **Read-Only Public Access:** Open for research, education, and exploration

## Technical Architecture (Separate Service)

- **Backend:** FastAPI service running independently of herbalist
- **Database:** PostgreSQL extension of existing estimabio database (new tables only)
- **Knowledge Graph:** Neo4j for relationship visualization
- **Frontend:** Static HTML/CSS/JS with interactive visualizations
- **Deployment:** Docker service in existing estimabio-compose.yml
- **Access:** Public read-only API and web interface

## Data Flow

```
Source Documents → LLM Entity Extraction → Normalization & Deduplication
                              ↓
                    Entity Resolution → Cultural/Geographic Linking  
                              ↓
                  Hierarchy Construction → Plant Connection Mapping
                              ↓
                   Neo4j Graph Population → PostgreSQL Storage
                              ↓
                      API Endpoints → Web Visualization
```

## Success Metrics

- Number of documented entities from diverse traditions
- Geographic and cultural coverage breadth  
- Academic source diversity and quality
- User engagement and research utility
- Integration with existing ethnobotanical databases
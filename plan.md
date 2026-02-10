# Refactoring Plan: Neo4j Knowledge Graph & RabbitMQ Integration

## Objective
Transition the Rock Family Tree Generator from a flat-file/Redis architecture to a persistent Knowledge Graph (Neo4j) for "depth-aware" caching and a robust messaging system (RabbitMQ) for service orchestration.

## 1. Infrastructure Requirements
- **Neo4j (v5.x):** Primary data store for bands, artists, and their relationships.
- **RabbitMQ:** Message broker for Celery tasks, replacing Redis.
- **Dependencies:** `neo4j` (Python driver), `celery` with RabbitMQ support.

## 2. Data Schema (Neo4j)
- **Nodes:**
  - `Band`: `{mbid, name, start_year, end_year, explored_depth, last_synced}`
  - `Artist`: `{mbid, name}`
- **Relationships:**
  - `(Artist)-[:MEMBER_OF {role, start_year, end_year, position}]->(Band)`

## 3. Implementation Steps

### Phase 1: Infrastructure Setup
- [x] Update `docker-compose.yml`:
  - Add `neo4j` service with persistence.
  - Replace `rftg-redis` with `rftg-rabbitmq`.
- [x] Update `backend/requirements.txt`: Add `neo4j`.
- [x] Update `.env`: Add Neo4j credentials and RabbitMQ URI.

### Phase 2: Knowledge Graph Layer
- [x] Create `backend/app/graph_db.py`:
  - `Neo4jClient` class for connection management.
  - `upsert_band_structure(data)`: Store MB data into the graph.
  - `get_cached_subgraph(mbid, depth)`: Check if coverage exists and return structured data.

### Phase 3: "Smart" Harvester Refactor
- [x] Modify `backend/app/harvester.py`:
  - Logic: Check Neo4j for `mbid` coverage at `requested_depth`.
  - If coverage is incomplete:
    - Identify missing nodes.
    - Fetch from MusicBrainz API.
    - Sync new data to Neo4j.
  - Return the full subgraph from Neo4j.

### Phase 4: Refiner & Data Flow
- [x] Update `backend/app/refiner.py`:
  - Adapt to process Neo4j node/relationship objects instead of raw JSON.
- [x] Update `backend/app/worker.py`:
  - Update Celery configuration for RabbitMQ.
  - Orchestrate the new Graph-first flow.

### Phase 5: Verification
- [/] Run end-to-end tests (Search -> Generate -> Neo4j Query -> SVG Verify).
- [ ] Validate portrait layout remains intact with new data source.

## 4. Testing Strategy
- **Unit Tests:** Verify `Neo4jClient` CRUD operations.
- **Integration Tests:** Verify `Harvester` only calls MusicBrainz when Neo4j depth is insufficient.
- **E2E Tests:** Generate a tree for a well-known band and verify relationships in Neo4j browser.

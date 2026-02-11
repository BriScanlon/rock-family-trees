# Rock Family Tree Generator (RFTG)

Procedurally generate high-fidelity, A1-printable "Rock Family Tree" posters. This application visualizes the connections between bands and their members, showing lineups, membership changes, and migrations between bands over time.

## 🏗 Architecture

The application follows a microservices architecture orchestrated by Docker Compose:

*   **Frontend**: A React application (Vite + Tailwind CSS) providing an interactive UI for searching bands, configuring generation parameters, and viewing/downloading the generated trees.
*   **Backend**: A FastAPI application that handles API requests, serves the frontend (if configured), and manages the generation process.
*   **Worker**: A Celery worker that performs the heavy lifting:
    1.  **Harvest**: Fetches data from MusicBrainz and syncs it to a Neo4j graph database.
    2.  **Refine**: Processes the raw graph data.
    3.  **Cartographer**: Calculates the layout (timeline, positioning) for the family tree.
    4.  **Artist**: Renders the final SVG poster.
*   **Message Broker**: RabbitMQ (`rftg-rabbitmq`) for managing the task queue between the backend and worker.
*   **Database**: Neo4j (`rftg-neo4j`) for storing the complex relationships between artists and bands.

## 🚀 Getting Started

### Prerequisites

*   Docker
*   Docker Compose

### Installation & Running

1.  Clone the repository.
2.  Create a `.env` file based on `sample.env` (if available) or ensure the defaults in `docker-compose.yml` are sufficient.
3.  Start the services:

    ```bash
    docker-compose up --build
    ```

4.  Access the application:
    *   **Frontend**: `http://localhost:5173` (default port, check `docker-compose.yml`)
    *   **Backend API**: `http://localhost:8000`
    *   **Neo4j Browser**: `http://localhost:7474`
    *   **RabbitMQ Management**: `http://localhost:15672`

## 📂 Project Structure

*   `backend/`: Python backend and worker code.
    *   `main.py`: FastAPI entry point.
    *   `app/`: Core logic modules.
        *   `harvester.py`: MusicBrainz data fetching and Neo4j syncing.
        *   `worker.py`: Celery task definitions.
        *   `artist.py`: SVG rendering logic.
        *   `cartographer.py`: Graph layout and positioning.
        *   `graph_db.py`: Neo4j interaction layer.
*   `frontend/`: React frontend code.
    *   `src/`: Components and application logic.
*   `docker-compose.yml`: Service orchestration configuration.

## 🔌 API Endpoints

*   `GET /search?q={query}`: Search for an artist/band by name.
*   `POST /generate`: Start a background job to generate a family tree.
    *   Body: `{"artist_id": "mbid", "depth": 2}`
*   `GET /status/{job_id}`: Check the status of a generation job.
*   `GET /download/{job_id}`: Download the generated SVG artifact.

## ✨ Features

*   **Interactive Search**: Find bands using the MusicBrainz database.
*   **Configurable Depth**: Control how deep the recursive search for band members and connections goes.
*   **Visual Feedback**: Real-time progress updates during the generation process.
*   **High-Quality Output**: Generates A1-sized SVG posters suitable for printing.
*   **Caching**: Utilizes Neo4j to cache artist data, reducing external API calls on subsequent runs.
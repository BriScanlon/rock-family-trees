# RFTG Backend & Worker

The backend services for the Rock Family Tree Generator, responsible for data harvesting, graph processing, layout calculation, and SVG rendering.

## 🏗 Architecture

The backend consists of two main components:
1.  **FastAPI Application (`main.py`)**: Handles HTTP requests for searching bands and triggering generation jobs.
2.  **Celery Worker (`app/worker.py`)**: Executes background tasks for fetching data and generating the family tree.

### Core Modules (`app/`)

*   `harvester.py`: Interacts with the MusicBrainz API to fetch artist data and syncs it to a Neo4j graph database. Implements rate limiting and recursive fetching.
*   `refiner.py`: Processes raw graph data from Neo4j to prepare it for layout calculation.
*   `cartographer.py`: Calculates the timeline and spatial layout of bands and members on the canvas.
*   **`artist.py`**: Uses `svgwrite` to render the final SVG poster based on the calculated layout.
*   `graph_db.py`: A Neo4j client wrapper for managing database interactions.

## 🚀 Getting Started

1.  Navigate to the `backend` directory:
    ```bash
    cd backend
    ```

2.  Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  Run the API server:
    ```bash
    uvicorn main:app --reload
    ```

5.  Run the Celery worker (in a separate terminal):
    ```bash
    celery -A app.worker worker --loglevel=info
    ```

## ⚙️ Environment Variables

Ensure these are set in your `.env` file or environment:

*   `RABBITMQ_URL`: Connection string for RabbitMQ (e.g., `pyamqp://guest:guest@localhost//`).
*   `BACKEND_PORT`: Port for the API server (default: `8000`).
*   `NEO4J_AUTH`: Authentication for Neo4j (e.g., `neo4j/password`).
*   `MB_USER_AGENT`: User agent string for MusicBrainz API requests.
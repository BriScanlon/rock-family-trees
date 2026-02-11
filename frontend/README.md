# RFTG Frontend

An interactive web interface for the Rock Family Tree Generator, built with React, Vite, and Tailwind CSS. It allows users to search for bands, configure generation parameters, and visualize the generated family trees.

## 🛠 Tech Stack

*   **Framework**: React (v18)
*   **Build Tool**: Vite
*   **Styling**: Tailwind CSS
*   **Icons**: Lucide React
*   **HTTP Client**: Axios

## 🚀 Getting Started

1.  Navigate to the `frontend` directory:
    ```bash
    cd frontend
    ```

2.  Install dependencies:
    ```bash
    npm install
    ```

3.  Start the development server:
    ```bash
    npm run dev
    ```

4.  Build for production:
    ```bash
    npm run build
    ```

## ⚙️ Configuration

The frontend uses environment variables (prefixed with `VITE_`) for configuration.

*   `VITE_BACKEND_PORT`: The port on which the backend API is running (default: `8000`).
*   `VITE_BACKEND_HOST`: The hostname of the backend (automatically detected or defaults to `localhost`).

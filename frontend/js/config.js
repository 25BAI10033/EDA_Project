/**
 * Data Detective - Runtime Backend Configuration
 *
 * For cloud deployments (e.g. Vercel frontend + Render/Railway/Fly/EC2 backend),
 * set your deployed FastAPI backend URL here:
 *   API_BASE_URL: "https://your-data-detective-api.onrender.com"
 *
 * For local development, leaving it empty ("") defaults to http://127.0.0.1:8000.
 * In production, if left empty, the application will display a clear configuration
 * prompt requiring the backend URL rather than attempting to call the frontend domain.
 */
window.DATA_DETECTIVE_CONFIG = {
  API_BASE_URL: ""
};

/**
 * Data Detective - Runtime Backend Configuration
 *
 * For unified Vercel deployments (where Vercel hosts both the static frontend
 * and the FastAPI serverless backend), leaving API_BASE_URL empty ("") automatically
 * connects to the deployed serverless backend on the same origin (window.location.origin).
 *
 * If you deploy the backend to a separate dedicated server (e.g. Render/Railway/Fly/EC2),
 * specify that backend URL here:
 *   API_BASE_URL: "https://your-data-detective-api.onrender.com"
 *
 * For local development, leaving it empty ("") defaults to http://127.0.0.1:8000.
 */
window.DATA_DETECTIVE_CONFIG = {
  API_BASE_URL: ""
};


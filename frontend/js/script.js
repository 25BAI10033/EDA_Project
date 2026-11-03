/**
 * Data Detective - Frontend Client Script
 * Handles backend health checks, dataset upload/preview, automated EDA, Data Cleaning Studio,
 * Interactive Visualization Studio, Automated Report Generation, and Multi-Format Exports.
 */

/**
 * Configurable FastAPI Backend URL resolution.
 *
 * Precedence:
 * 1. window.DATA_DETECTIVE_CONFIG?.API_BASE_URL (from js/config.js or build-time configuration)
 * 2. window.DATA_DETECTIVE_API_URL or window.API_BASE_URL
 * 3. HTML meta tag: <meta name="api-base-url" content="...">
 * 4. Browser localStorage: "DATA_DETECTIVE_API_URL" or "API_BASE_URL"
 * 5. Local development fallback: "http://127.0.0.1:8000" when running frontend locally (e.g. localhost:3000)
 * 6. Deployed Vercel fallback: window.location.origin (unified deployment where Vercel routes both frontend and FastAPI)
 */
function getApiBaseUrl() {
  if (typeof window !== "undefined" && window.DATA_DETECTIVE_CONFIG && window.DATA_DETECTIVE_CONFIG.API_BASE_URL) {
    const raw = String(window.DATA_DETECTIVE_CONFIG.API_BASE_URL).trim().replace(/\/+$/, "");
    if (raw) return raw;
  }
  if (typeof window !== "undefined" && window.DATA_DETECTIVE_API_URL) {
    const raw = String(window.DATA_DETECTIVE_API_URL).trim().replace(/\/+$/, "");
    if (raw) return raw;
  }
  if (typeof window !== "undefined" && window.API_BASE_URL && typeof window.API_BASE_URL === "string") {
    const raw = String(window.API_BASE_URL).trim().replace(/\/+$/, "");
    if (raw) return raw;
  }
  if (typeof document !== "undefined") {
    const metaTag = document.querySelector('meta[name="api-base-url"]');
    if (metaTag && metaTag.content && metaTag.content.trim()) {
      return metaTag.content.trim().replace(/\/+$/, "");
    }
  }
  try {
    const stored = window.localStorage.getItem("DATA_DETECTIVE_API_URL") || window.localStorage.getItem("API_BASE_URL");
    if (stored && stored.trim()) {
      return stored.trim().replace(/\/+$/, "");
    }
  } catch (e) {}

  if (typeof window !== "undefined" && window.location) {
    const hostname = window.location.hostname;
    if (hostname === "localhost" || hostname === "127.0.0.1" || hostname === "0.0.0.0") {
      if (window.location.port !== "8000") {
        return "http://127.0.0.1:8000";
      }
    }
    if (window.location.origin && window.location.protocol && window.location.protocol.startsWith("http")) {
      return window.location.origin;
    }
  }

  return "http://127.0.0.1:8000";
}

/**
 * Validate that the backend URL is configured before initiating data requests.
 * If unconfigured, shows a clear error and smoothly scrolls to the diagnostics configuration box.
 */
function checkBackendConfigured() {
  const url = getApiBaseUrl();
  if (!url) {
    const isVercel = typeof window !== "undefined" && window.location && window.location.hostname.includes("vercel.app");
    const deployName = isVercel ? "Vercel deployment" : "remote deployment";
    showError(`FastAPI Backend URL is not configured for this ${deployName}. Please configure your backend URL in the System Status & Diagnostics section below.`);
    const diagSection = document.querySelector(".diagnostics-card");
    if (diagSection) {
      diagSection.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    const inputUrl = document.getElementById("inputBackendUrl");
    if (inputUrl) {
      inputUrl.focus();
    }
    return null;
  }
  return url;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = [".csv", ".xlsx", ".json", ".jsonl", ".ndjson"];

/**
 * Format error details safely to prevent [object Object] serialization in UI.
 */
function formatErrorMessage(detail, fallback = "An unexpected error occurred.") {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map(item => item.msg || item.message || JSON.stringify(item)).join(", ");
  }
  if (typeof detail === "object") {
    if (detail.message) return detail.message;
    if (detail.detail) return formatErrorMessage(detail.detail, fallback);
    return JSON.stringify(detail);
  }
  return String(detail);
}

// DOM Elements - Health & Diagnostics (Phase 1)
const statusBadge = document.getElementById("statusBadge");
const statusText = document.getElementById("statusText");
const healthStatusValue = document.getElementById("healthStatusValue");
const apiRootMessage = document.getElementById("apiRootMessage");
const diagnosticsOutput = document.getElementById("diagnosticsOutput");
const btnCheckHealth = document.getElementById("btnCheckHealth");
const apiServerUrl = document.getElementById("apiServerUrl");
const apiDocsLink = document.getElementById("apiDocsLink");
const inputBackendUrl = document.getElementById("inputBackendUrl");
const btnSaveBackendUrl = document.getElementById("btnSaveBackendUrl");
const btnResetBackendUrl = document.getElementById("btnResetBackendUrl");

// DOM Elements - Alerts
const errorAlert = document.getElementById("errorAlert");
const errorMessage = document.getElementById("errorMessage");
const btnDismissError = document.getElementById("btnDismissError");

// DOM Elements - Upload & Dropzone (Phase 2)
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const fileStage = document.getElementById("fileStage");
const stagedFileName = document.getElementById("stagedFileName");
const stagedFileSize = document.getElementById("stagedFileSize");
const btnUpload = document.getElementById("btnUpload");
const btnCancelStage = document.getElementById("btnCancelStage");

// DOM Elements - Upload Progress
const uploadProgressContainer = document.getElementById("uploadProgressContainer");
const uploadProgressBar = document.getElementById("uploadProgressBar");
const uploadProgressLabel = document.getElementById("uploadProgressLabel");
const uploadProgressPercent = document.getElementById("uploadProgressPercent");

// DOM Elements - Phase 2 Results
const resultsSection = document.getElementById("resultsSection");
const statFileName = document.getElementById("statFileName");
const statFileFormat = document.getElementById("statFileFormat");
const statFileSize = document.getElementById("statFileSize");
const statRowCount = document.getElementById("statRowCount");
const statColCount = document.getElementById("statColCount");
const previewTableHead = document.getElementById("previewTableHead");
const previewTableBody = document.getElementById("previewTableBody");
const schemaTableBody = document.getElementById("schemaTableBody");
const btnUploadAnother = document.getElementById("btnUploadAnother");

// DOM Elements - Phase 3 Automated EDA
const btnRunAnalysis = document.getElementById("btnRunAnalysis");
const analysisLoading = document.getElementById("analysisLoading");
const edaDashboardSection = document.getElementById("edaDashboardSection");
const btnScrollToTop = document.getElementById("btnScrollToTop");
const btnGoToCleanerFromEda = document.getElementById("btnGoToCleanerFromEda");

// Statistical Summary Tabs
const btnTabNumStats = document.getElementById("btnTabNumStats");
const btnTabCatStats = document.getElementById("btnTabCatStats");
const numericalStatsContainer = document.getElementById("numericalStatsContainer");
const categoricalStatsContainer = document.getElementById("categoricalStatsContainer");
const numStatsHead = document.getElementById("numStatsHead");
const numStatsBody = document.getElementById("numStatsBody");
const catStatsHead = document.getElementById("catStatsHead");
const catStatsBody = document.getElementById("catStatsBody");

// Missing Values & Duplicates
const missingTableBody = document.getElementById("missingTableBody");
const duplicateStatusBanner = document.getElementById("duplicateStatusBanner");
const dupBannerIcon = document.getElementById("dupBannerIcon");
const dupBannerTitle = document.getElementById("dupBannerTitle");
const dupBannerDesc = document.getElementById("dupBannerDesc");
const columnAnalysisBody = document.getElementById("columnAnalysisBody");

// Outliers & Correlation
const outliersTableBody = document.getElementById("outliersTableBody");
const correlationHead = document.getElementById("correlationHead");
const correlationBody = document.getElementById("correlationBody");
const correlationSubtitle = document.getElementById("correlationSubtitle");
const topCorrelationsBadges = document.getElementById("topCorrelationsBadges");

// Distribution Visualizer
const selectDistColumn = document.getElementById("selectDistColumn");
const distMetaBar = document.getElementById("distMetaBar");
const chartContainer = document.getElementById("chartContainer");

// DOM Elements - Phase 4 Cleaning Studio
const btnOpenCleaningStudio = document.getElementById("btnOpenCleaningStudio");
const cleaningStudioSection = document.getElementById("cleaningStudioSection");
const btnScrollToPreview = document.getElementById("btnScrollToPreview");

const chkDropDuplicates = document.getElementById("chkDropDuplicates");

const selectMissingCol = document.getElementById("selectMissingCol");
const selectMissingStrategy = document.getElementById("selectMissingStrategy");
const groupCustomMissingVal = document.getElementById("groupCustomMissingVal");
const inputCustomMissingVal = document.getElementById("inputCustomMissingVal");
const btnAddMissingOp = document.getElementById("btnAddMissingOp");

const selectTypeCol = document.getElementById("selectTypeCol");
const selectTargetType = document.getElementById("selectTargetType");
const btnAddTypeOp = document.getElementById("btnAddTypeOp");

const selectOutlierCol = document.getElementById("selectOutlierCol");
const selectOutlierAction = document.getElementById("selectOutlierAction");
const btnAddOutlierOp = document.getElementById("btnAddOutlierOp");

const selectEncodeCol = document.getElementById("selectEncodeCol");
const selectEncodeMethod = document.getElementById("selectEncodeMethod");
const btnAddEncodeOp = document.getElementById("btnAddEncodeOp");

const selectScaleCol = document.getElementById("selectScaleCol");
const selectScaleMethod = document.getElementById("selectScaleMethod");
const btnAddScaleOp = document.getElementById("btnAddScaleOp");

const selectRenameCol = document.getElementById("selectRenameCol");
const inputNewColName = document.getElementById("inputNewColName");
const btnAddRenameOp = document.getElementById("btnAddRenameOp");

const selectDropCol = document.getElementById("selectDropCol");
const btnAddDropOp = document.getElementById("btnAddDropOp");

const pipelineCountBadge = document.getElementById("pipelineCountBadge");
const pipelineList = document.getElementById("pipelineList");
const btnPreviewClean = document.getElementById("btnPreviewClean");
const btnClearPipeline = document.getElementById("btnClearPipeline");

const cleanLoading = document.getElementById("cleanLoading");
const cleanPreviewContainer = document.getElementById("cleanPreviewContainer");
const btnApplyCleaned = document.getElementById("btnApplyCleaned");

const diffRows = document.getElementById("diffRows");
const diffRowsSub = document.getElementById("diffRowsSub");
const diffCols = document.getElementById("diffCols");
const diffColsSub = document.getElementById("diffColsSub");
const diffOpsCount = document.getElementById("diffOpsCount");
const operationsLogList = document.getElementById("operationsLogList");

const btnTabCleanedPreview = document.getElementById("btnTabCleanedPreview");
const btnTabOriginalPreview = document.getElementById("btnTabOriginalPreview");
const cleanedTableContainer = document.getElementById("cleanedTableContainer");
const originalTableContainer = document.getElementById("originalTableContainer");
const cleanedTableHead = document.getElementById("cleanedTableHead");
const cleanedTableBody = document.getElementById("cleanedTableBody");
const originalTableHead = document.getElementById("originalTableHead");
const originalTableBody = document.getElementById("originalTableBody");

const btnDownloadCsv = document.getElementById("btnDownloadCsv");
const btnDownloadXlsx = document.getElementById("btnDownloadXlsx");
const btnDownloadJson = document.getElementById("btnDownloadJson");

// DOM Elements - Phase 5 Visualization Studio
const btnOpenVisualizationStudio = document.getElementById("btnOpenVisualizationStudio");
const btnGoToVisFromEda = document.getElementById("btnGoToVisFromEda");
const btnGoToVisFromCleaner = document.getElementById("btnGoToVisFromCleaner");
const btnVisScrollToCleaning = document.getElementById("btnVisScrollToCleaning");
const btnVisScrollToTop = document.getElementById("btnVisScrollToTop");
const visualizationStudioSection = document.getElementById("visualizationStudioSection");

// Source Switcher
const btnSourceOriginal = document.getElementById("btnSourceOriginal");
const btnSourceCleaned = document.getElementById("btnSourceCleaned");
const labelSourceOriginal = document.getElementById("labelSourceOriginal");
const labelSourceCleaned = document.getElementById("labelSourceCleaned");
const activeSourceInfo = document.getElementById("activeSourceInfo");
const activeSourceDetails = document.getElementById("activeSourceDetails");

// Controls
const visChartType = document.getElementById("visChartType");
const groupVisXCol = document.getElementById("groupVisXCol");
const lblVisXCol = document.getElementById("lblVisXCol");
const visXCol = document.getElementById("visXCol");
const groupVisYCol = document.getElementById("groupVisYCol");
const lblVisYCol = document.getElementById("lblVisYCol");
const visYCol = document.getElementById("visYCol");
const groupVisAggregation = document.getElementById("groupVisAggregation");
const lblVisAggregation = document.getElementById("lblVisAggregation");
const visAggregation = document.getElementById("visAggregation");
const visChartTitle = document.getElementById("visChartTitle");
const visHeatmapNotice = document.getElementById("visHeatmapNotice");
const visErrorAlert = document.getElementById("visErrorAlert");
const visErrorMessage = document.getElementById("visErrorMessage");
const btnDismissVisError = document.getElementById("btnDismissVisError");
const btnGenerateChart = document.getElementById("btnGenerateChart");
const btnResetVisControls = document.getElementById("btnResetVisControls");
const visLoadingIndicator = document.getElementById("visLoadingIndicator");

// Dashboard
const dashboardCountBadge = document.getElementById("dashboardCountBadge");
const btnRegenerateAllCharts = document.getElementById("btnRegenerateAllCharts");
const btnDownloadAllCharts = document.getElementById("btnDownloadAllCharts");
const btnClearDashboard = document.getElementById("btnClearDashboard");
const visEmptyState = document.getElementById("visEmptyState");
const chartsDashboardGrid = document.getElementById("chartsDashboardGrid");

// In-memory state
let stagedFile = null;
let currentUploadedFile = null;
let activeDatasetColumns = [];
let activeDatasetTypes = {};
let activeAnalysisData = null;
let queuedCleaningOperations = [];

// Phase 5 State
let originalDatasetFile = null;
let cleanedDatasetFile = null;
let originalDatasetMeta = null;
let cleanedDatasetMeta = null;
let activeVisSource = "original";
let dashboardCharts = [];

// Phase 6: Automated EDA Report Generation Studio
const reportStudioSection = document.getElementById("reportStudioSection");
const btnOpenReportStudio = document.getElementById("btnOpenReportStudio");
const btnGoToReportFromEda = document.getElementById("btnGoToReportFromEda");
const btnGoToReportFromCleaner = document.getElementById("btnGoToReportFromCleaner");
const btnGoToReportFromVis = document.getElementById("btnGoToReportFromVis");
const btnReportScrollToVis = document.getElementById("btnReportScrollToVis");
const btnReportScrollToCleaning = document.getElementById("btnReportScrollToCleaning");
const btnReportScrollToTop = document.getElementById("btnReportScrollToTop");
const btnReportSourceOriginal = document.getElementById("btnReportSourceOriginal");
const btnReportSourceCleaned = document.getElementById("btnReportSourceCleaned");
const labelReportSourceOriginal = document.getElementById("labelReportSourceOriginal");
const labelReportSourceCleaned = document.getElementById("labelReportSourceCleaned");
const activeReportSourceDetails = document.getElementById("activeReportSourceDetails");
const reportErrorAlert = document.getElementById("reportErrorAlert");
const reportErrorMessage = document.getElementById("reportErrorMessage");
const btnDismissReportError = document.getElementById("btnDismissReportError");
const reportSuccessAlert = document.getElementById("reportSuccessAlert");
const reportSuccessMessage = document.getElementById("reportSuccessMessage");
const btnDismissReportSuccess = document.getElementById("btnDismissReportSuccess");
const btnGenerateReport = document.getElementById("btnGenerateReport");
const btnDownloadReportAgain = document.getElementById("btnDownloadReportAgain");
const reportLoadingIndicator = document.getElementById("reportLoadingIndicator");
const reportLoadingText = document.getElementById("reportLoadingText");

let activeReportSource = "original";
let lastGeneratedReportBlob = null;
let lastGeneratedReportFileName = null;

/* -------------------------------------------------------------
 * 1. Backend Connectivity & Health Check (Phase 1)
 * ------------------------------------------------------------- */
async function checkBackendHealth() {
  const currentBaseUrl = getApiBaseUrl();

  if (inputBackendUrl && currentBaseUrl) {
    inputBackendUrl.value = currentBaseUrl;
  }

  if (!currentBaseUrl) {
    setUnconfiguredHealthState();
    return;
  }

  setLoadingHealthState(currentBaseUrl);

  try {
    const startTime = performance.now();

    // 1. Verify health status from primary or fallback health route
    let healthData = null;
    let healthResponse = await fetch(`${currentBaseUrl}/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!healthResponse.ok) {
      healthResponse = await fetch(`${currentBaseUrl}/api/health`, {
        method: "GET",
        headers: { Accept: "application/json" },
      });
    }

    if (!healthResponse.ok) {
      throw new Error(`HTTP error ${healthResponse.status}: ${healthResponse.statusText}`);
    }

    healthData = await healthResponse.json();
    const durationMs = Math.round(performance.now() - startTime);

    // 2. Fetch root API information safely without failing if root is the static frontend HTML
    let rootData = null;
    try {
      const isUnifiedHost = typeof window !== "undefined" && window.location && (currentBaseUrl === window.location.origin || currentBaseUrl === "");
      const rootUrl = isUnifiedHost ? `${currentBaseUrl}/api` : `${currentBaseUrl}/`;

      const rootResponse = await fetch(rootUrl, {
        method: "GET",
        headers: { Accept: "application/json" },
      });

      if (rootResponse.ok) {
        const contentType = rootResponse.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          rootData = await rootResponse.json();
        }
      }

      if (!rootData && isUnifiedHost) {
        const fallbackResponse = await fetch(`${currentBaseUrl}/`, {
          method: "GET",
          headers: { Accept: "application/json" },
        });
        if (fallbackResponse.ok) {
          const contentType = fallbackResponse.headers.get("content-type") || "";
          if (contentType.includes("application/json")) {
            rootData = await fallbackResponse.json();
          }
        }
      }
    } catch (e) {
      console.warn("Non-critical: could not fetch root info JSON:", e);
    }

    setHealthyHealthState(healthData, rootData, durationMs, currentBaseUrl);
  } catch (error) {
    setUnhealthyHealthState(error.message, currentBaseUrl);
  }
}

function setUnconfiguredHealthState() {
  if (statusBadge) {
    statusBadge.className = "badge-status unhealthy";
    statusText.textContent = "Backend: Not Configured";
  }
  if (healthStatusValue) {
    healthStatusValue.textContent = "Missing Configuration";
  }
  if (apiRootMessage) {
    apiRootMessage.textContent = "No backend URL set";
  }
  if (apiServerUrl) {
    apiServerUrl.textContent = "Not Configured (Missing API_BASE_URL)";
    apiServerUrl.style.color = "var(--status-red)";
  }
  if (apiDocsLink) {
    apiDocsLink.removeAttribute("href");
    apiDocsLink.style.pointerEvents = "none";
    apiDocsLink.style.opacity = "0.5";
    apiDocsLink.title = "Configure backend URL to view Swagger docs";
  }
  if (diagnosticsOutput) {
    const origin = typeof window !== "undefined" && window.location ? window.location.origin : "unknown host";
    diagnosticsOutput.textContent =
      `[${new Date().toISOString()}] Configuration Notice:\n` +
      `No FastAPI backend URL is configured for this deployment.\n\n` +
      `Frontend Origin: ${origin}\n` +
      `The frontend will never attempt to call the Vercel frontend URL as the FastAPI backend.\n\n` +
      `How to connect your backend:\n` +
      `1. Enter your deployed FastAPI backend URL above (e.g. https://your-backend.onrender.com) and click 'Save & Connect'.\n` +
      `2. Or define window.DATA_DETECTIVE_CONFIG = { API_BASE_URL: "https://your-backend.com" } in frontend/js/config.js.`;
  }
}

function setLoadingHealthState(baseUrl) {
  if (statusBadge) {
    statusBadge.className = "badge-status";
    statusText.textContent = "Checking Backend...";
  }
  if (healthStatusValue) {
    healthStatusValue.textContent = "Connecting...";
  }
  if (apiServerUrl && baseUrl) {
    apiServerUrl.textContent = baseUrl;
    apiServerUrl.style.color = "inherit";
  }
  if (apiDocsLink && baseUrl) {
    apiDocsLink.href = `${baseUrl}/docs`;
    apiDocsLink.style.pointerEvents = "auto";
    apiDocsLink.style.opacity = "1";
    apiDocsLink.title = "Open interactive Swagger docs";
  }
}

function setHealthyHealthState(healthData, rootData, durationMs, baseUrl) {
  if (statusBadge) {
    statusBadge.className = "badge-status healthy";
    statusText.textContent = `Backend: ${healthData.status || "Healthy"}`;
  }
  if (healthStatusValue) {
    healthStatusValue.textContent = `${healthData.status || "healthy"} (${durationMs}ms)`;
  }
  if (apiRootMessage && rootData) {
    apiRootMessage.textContent = rootData.message || "OK";
  }
  if (apiServerUrl && baseUrl) {
    apiServerUrl.textContent = baseUrl;
    apiServerUrl.style.color = "inherit";
  }
  if (apiDocsLink && baseUrl) {
    apiDocsLink.href = `${baseUrl}/docs`;
    apiDocsLink.style.pointerEvents = "auto";
    apiDocsLink.style.opacity = "1";
    apiDocsLink.title = "Open interactive Swagger docs";
  }
  if (diagnosticsOutput) {
    diagnosticsOutput.textContent = JSON.stringify(
      {
        timestamp: new Date().toISOString(),
        backendUrl: baseUrl,
        latency: `${durationMs}ms`,
        healthCheck: healthData,
        rootEndpoint: rootData,
      },
      null,
      2
    );
  }
}

function setUnhealthyHealthState(errorMsg, baseUrl) {
  if (statusBadge) {
    statusBadge.className = "badge-status unhealthy";
    statusText.textContent = "Backend Offline";
  }
  if (healthStatusValue) {
    healthStatusValue.textContent = "Connection Failed";
  }
  if (apiRootMessage) {
    apiRootMessage.textContent = "Unavailable";
  }
  if (apiServerUrl && baseUrl) {
    apiServerUrl.textContent = baseUrl;
    apiServerUrl.style.color = "var(--status-red)";
  }
  if (apiDocsLink && baseUrl) {
    apiDocsLink.href = `${baseUrl}/docs`;
    apiDocsLink.style.pointerEvents = "auto";
    apiDocsLink.style.opacity = "1";
  }
  if (diagnosticsOutput) {
    diagnosticsOutput.textContent = `[${new Date().toISOString()}] Connection Error:\n` +
      `Failed to reach backend at ${baseUrl}.\n` +
      `Details: ${errorMsg}\n\n` +
      `Troubleshooting:\n` +
      `1. Verify that the FastAPI backend service is running and accessible at ${baseUrl}.\n` +
      `2. Ensure CORS is enabled on the backend (check ALLOWED_ORIGINS in .env).\n` +
      `3. For local development, start the backend with:\n` +
      `   .\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload`;
  }
}

/* -------------------------------------------------------------
 * 2. Alert & Utility Helpers
 * ------------------------------------------------------------- */
function showError(msg) {
  if (errorMessage && errorAlert) {
    errorMessage.textContent = msg;
    errorAlert.style.display = "flex";
    errorAlert.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function dismissError() {
  if (errorAlert) {
    errorAlert.style.display = "none";
  }
}

function showVisError(msg) {
  if (visErrorMessage && visErrorAlert) {
    visErrorMessage.textContent = msg;
    visErrorAlert.style.display = "flex";
    visErrorAlert.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function dismissVisError() {
  if (visErrorAlert) {
    visErrorAlert.style.display = "none";
  }
}

if (btnDismissVisError) {
  btnDismissVisError.addEventListener("click", dismissVisError);
}

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/* -------------------------------------------------------------
 * 3. Drag and Drop & File Staging (Phase 2)
 * ------------------------------------------------------------- */
function validateFile(file) {
  if (!file) {
    showError("No file selected.");
    return false;
  }

  const fileName = file.name.toLowerCase();
  const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => fileName.endsWith(ext));

  if (!hasValidExt) {
    showError("Unsupported file format. Please upload a CSV (.csv), Excel (.xlsx), or JSON (.json, .jsonl) file.");
    return false;
  }

  if (file.size === 0) {
    showError("The selected file is empty (0 bytes).");
    return false;
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    showError(`File size exceeds 10 MB limit (${formatBytes(file.size)}).`);
    return false;
  }

  dismissError();
  return true;
}

function stageSelectedFile(file) {
  if (!validateFile(file)) {
    return;
  }

  stagedFile = file;
  stagedFileName.textContent = file.name;
  stagedFileSize.textContent = formatBytes(file.size);

  fileStage.style.display = "flex";
  uploadProgressContainer.style.display = "none";
}

function resetStaging() {
  stagedFile = null;
  currentUploadedFile = null;
  originalDatasetFile = null;
  cleanedDatasetFile = null;
  originalDatasetMeta = null;
  cleanedDatasetMeta = null;
  activeVisSource = "original";
  clearDashboardCharts();
  updateVisDatasetSwitcherUI();

  activeDatasetColumns = [];
  activeDatasetTypes = {};
  activeAnalysisData = null;
  queuedCleaningOperations = [];
  updatePipelineQueueUI();

  fileInput.value = "";
  fileStage.style.display = "none";
  uploadProgressContainer.style.display = "none";
}

// Drag & Drop Event Listeners
if (dropZone) {
  dropZone.addEventListener("click", () => {
    fileInput.click();
  });

  dropZone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("dragover");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      stageSelectedFile(files[0]);
    }
  });
}

if (fileInput) {
  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      stageSelectedFile(e.target.files[0]);
    }
  });
}

if (btnCancelStage) {
  btnCancelStage.addEventListener("click", () => {
    resetStaging();
  });
}

if (btnDismissError) {
  btnDismissError.addEventListener("click", () => {
    dismissError();
  });
}

/* -------------------------------------------------------------
 * 4. Dataset Upload & Preview (Phase 2)
 * ------------------------------------------------------------- */
async function uploadAndInspectDataset() {
  if (!stagedFile) {
    showError("Please select a file to upload.");
    return;
  }

  const baseUrl = checkBackendConfigured();
  if (!baseUrl) {
    if (btnUpload) btnUpload.disabled = false;
    if (uploadProgressContainer) uploadProgressContainer.style.display = "none";
    return;
  }

  dismissError();
  btnUpload.disabled = true;
  uploadProgressContainer.style.display = "block";
  setProgress(25, "Uploading file to server...");

  const formData = new FormData();
  formData.append("file", stagedFile);
  currentUploadedFile = stagedFile; // Keep in-memory file reference

  try {
    setProgress(55, "Reading and parsing dataset with Pandas...");

    const response = await fetch(`${baseUrl}/api/upload`, {
      method: "POST",
      body: formData,
    });

    setProgress(90, "Processing metadata...");

    const data = await response.json();

    if (!response.ok) {
      const errorMsg = data && data.detail ? data.detail : `Server error (${response.status}): ${response.statusText}`;
      throw new Error(errorMsg);
    }

    setProgress(100, "Rendering dataset preview...");

    activeDatasetColumns = data.columns || [];
    activeDatasetTypes = data.data_types || {};

    renderDatasetPreview(data);
    populateCleaningDropdowns(activeDatasetColumns, activeDatasetTypes);

    // Record dataset for Phase 5 Visualization Studio
    if (!currentUploadedFile.name.startsWith("cleaned_")) {
      originalDatasetFile = currentUploadedFile;
      originalDatasetMeta = {
        filename: data.filename || currentUploadedFile.name,
        row_count: data.row_count,
        column_count: data.column_count,
        columns: data.columns || [],
        data_types: data.data_types || {},
      };
    } else {
      cleanedDatasetFile = currentUploadedFile;
      cleanedDatasetMeta = {
        filename: data.filename || currentUploadedFile.name,
        row_count: data.row_count,
        column_count: data.column_count,
        columns: data.columns || [],
        data_types: data.data_types || {},
      };
    }
    updateVisDatasetSwitcherUI();
    updateReportDatasetSwitcherUI();
    updateReportDatasetSwitcherUI();
    populateVisualizationDropdowns();

    fileStage.style.display = "none";
    uploadProgressContainer.style.display = "none";
  } catch (error) {
    showError(error.message || "Failed to upload and process dataset.");
    uploadProgressContainer.style.display = "none";
  } finally {
    btnUpload.disabled = false;
  }
}

function setProgress(percent, label) {
  if (uploadProgressBar) {
    uploadProgressBar.style.width = `${percent}%`;
  }
  if (uploadProgressPercent) {
    uploadProgressPercent.textContent = `${percent}%`;
  }
  if (uploadProgressLabel) {
    uploadProgressLabel.textContent = label;
  }
}

function detectClientFileFormat(fileName) {
  const lower = (fileName || "").toLowerCase();
  if (lower.endsWith(".csv")) return "CSV";
  if (lower.endsWith(".xlsx")) return "Excel (.xlsx)";
  if (lower.endsWith(".jsonl") || lower.endsWith(".ndjson")) return "JSON Lines";
  if (lower.endsWith(".json")) return "JSON";
  return "Dataset";
}

function renderDatasetPreview(data) {
  if (statFileName) statFileName.textContent = data.filename || "dataset";
  if (statFileFormat) {
    statFileFormat.textContent = data.file_format || detectClientFileFormat(data.filename || "");
    statFileFormat.style.display = "inline-block";
  }
  if (statFileSize) statFileSize.textContent = formatBytes(data.file_size);
  if (statRowCount) statRowCount.textContent = (data.row_count || 0).toLocaleString();
  if (statColCount) statColCount.textContent = (data.column_count || 0).toLocaleString();

  // Render Preview Table Headers
  if (previewTableHead) {
    previewTableHead.innerHTML = "";
    const headRow = document.createElement("tr");

    const indexTh = document.createElement("th");
    indexTh.className = "row-index-cell";
    indexTh.textContent = "#";
    headRow.appendChild(indexTh);

    (data.columns || []).forEach((colName) => {
      const th = document.createElement("th");
      th.textContent = colName;
      headRow.appendChild(th);
    });

    previewTableHead.appendChild(headRow);
  }

  // Render Preview Table Body (First 5 rows)
  if (previewTableBody) {
    previewTableBody.innerHTML = "";

    const previewRows = data.preview || [];
    if (previewRows.length === 0) {
      const emptyRow = document.createElement("tr");
      const emptyTd = document.createElement("td");
      emptyTd.colSpan = (data.columns ? data.columns.length : 0) + 1;
      emptyTd.textContent = "No preview rows available.";
      emptyTd.style.textAlign = "center";
      emptyRow.appendChild(emptyTd);
      previewTableBody.appendChild(emptyRow);
    } else {
      previewRows.forEach((row, rowIndex) => {
        const tr = document.createElement("tr");

        const indexTd = document.createElement("td");
        indexTd.className = "row-index-cell";
        indexTd.textContent = rowIndex + 1;
        tr.appendChild(indexTd);

        (data.columns || []).forEach((col) => {
          const td = document.createElement("td");
          const val = row[col];

          if (val === null || val === undefined) {
            td.innerHTML = `<span class="null-pill">null</span>`;
          } else {
            td.textContent = String(val);
          }
          tr.appendChild(td);
        });

        previewTableBody.appendChild(tr);
      });
    }
  }

  // Render Column Schema Table
  if (schemaTableBody) {
    schemaTableBody.innerHTML = "";

    const columns = data.columns || [];
    const dataTypes = data.data_types || {};

    columns.forEach((colName, index) => {
      const tr = document.createElement("tr");

      const indexTd = document.createElement("td");
      indexTd.className = "row-index-cell";
      indexTd.textContent = index + 1;

      const nameTd = document.createElement("td");
      nameTd.style.fontWeight = "600";
      nameTd.textContent = colName;

      const typeTd = document.createElement("td");
      const typeBadge = document.createElement("span");
      typeBadge.className = "type-pill";
      typeBadge.textContent = dataTypes[colName] || "unknown";
      typeTd.appendChild(typeBadge);

      tr.appendChild(indexTd);
      tr.appendChild(nameTd);
      tr.appendChild(typeTd);
      schemaTableBody.appendChild(tr);
    });
  }

  if (resultsSection) {
    resultsSection.style.display = "block";
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

/* -------------------------------------------------------------
 * 5. Phase 3: Automated EDA Dashboard Execution & Rendering
 * ------------------------------------------------------------- */
async function runAutomatedAnalysis() {
  const fileToAnalyze = currentUploadedFile || stagedFile;

  if (!fileToAnalyze) {
    showError("No active dataset to analyze. Please upload a CSV or Excel file first.");
    return;
  }

  const baseUrl = checkBackendConfigured();
  if (!baseUrl) {
    if (btnRunAnalysis) {
      btnRunAnalysis.disabled = false;
      btnRunAnalysis.innerHTML = `<span class="btn-icon-symbol">&#128269;</span> Run Automated Analysis`;
    }
    if (analysisLoading) analysisLoading.style.display = "none";
    return;
  }

  dismissError();
  if (btnRunAnalysis) {
    btnRunAnalysis.disabled = true;
    btnRunAnalysis.innerHTML = `<span class="btn-icon-symbol">&#8987;</span> Analyzing...`;
  }

  if (analysisLoading) {
    analysisLoading.style.display = "flex";
    analysisLoading.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  const formData = new FormData();
  formData.append("file", fileToAnalyze);

  try {
    const response = await fetch(`${baseUrl}/api/analyze`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      const errorMsg = data && data.detail ? data.detail : `Server error (${response.status}): ${response.statusText}`;
      throw new Error(errorMsg);
    }

    activeAnalysisData = data;
    renderEdaDashboard(data);

    if (analysisLoading) {
      analysisLoading.style.display = "none";
    }

    if (edaDashboardSection) {
      edaDashboardSection.style.display = "block";
      edaDashboardSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (error) {
    showError(error.message || "Failed to perform automated exploratory data analysis.");
    if (analysisLoading) {
      analysisLoading.style.display = "none";
    }
  } finally {
    if (btnRunAnalysis) {
      btnRunAnalysis.disabled = false;
      btnRunAnalysis.innerHTML = `<span class="btn-icon-symbol">&#9881;</span> Re-analyze Dataset`;
    }
  }
}

function renderEdaDashboard(data) {
  renderOverviewCards(data.overview, data.missing_values, data.duplicates, data.outliers);
  renderStatisticalSummary(data.statistical_summary);
  renderMissingValuesTable(data.missing_values);
  renderDuplicatesAndProfiles(data.duplicates, data.column_analysis);
  renderOutliersTable(data.outliers);
  renderCorrelationMatrix(data.correlation);
  setupDistributionVisualizer(data.distributions, data.column_analysis);
}

function renderOverviewCards(overview, missing, duplicates, outliers) {
  const elRows = document.getElementById("edaTotalRows");
  const elRowsSub = document.getElementById("edaRowsSubtext");
  const elCols = document.getElementById("edaTotalCols");
  const elColsSub = document.getElementById("edaColsSubtext");
  const elMem = document.getElementById("edaMemory");
  const elMissPct = document.getElementById("edaMissingPct");
  const elMissSub = document.getElementById("edaMissingSubtext");
  const elDups = document.getElementById("edaDuplicates");
  const elDupsSub = document.getElementById("edaDuplicatesSubtext");
  const elOutliers = document.getElementById("edaOutliersTotal");

  if (elRows) elRows.textContent = (overview.total_rows || 0).toLocaleString();
  if (elRowsSub) elRowsSub.textContent = `${(duplicates.unique_rows_count || overview.total_rows).toLocaleString()} unique rows`;

  if (elCols) elCols.textContent = (overview.total_columns || 0).toLocaleString();
  if (elColsSub) elColsSub.textContent = `${overview.numerical_columns_count} numerical, ${overview.categorical_columns_count} categorical`;

  if (elMem) elMem.textContent = overview.memory_usage_formatted || "-";

  const overallMiss = missing.overall || {};
  if (elMissPct) elMissPct.textContent = `${overallMiss.overall_missing_percentage || 0}%`;
  if (elMissSub) elMissSub.textContent = `${(overallMiss.total_missing_cells || 0).toLocaleString()} of ${(overallMiss.total_cells || 0).toLocaleString()} cells`;

  if (elDups) elDups.textContent = (duplicates.duplicate_count || 0).toLocaleString();
  if (elDupsSub) elDupsSub.textContent = `${duplicates.duplicate_percentage}% duplicate rate`;

  if (elOutliers) elOutliers.textContent = (outliers.total_outliers_detected || 0).toLocaleString();
}

function renderStatisticalSummary(stats) {
  const numData = stats.numerical || {};
  const catData = stats.categorical || {};

  const numCols = Object.keys(numData);
  const catCols = Object.keys(catData);

  if (numStatsHead && numStatsBody) {
    numStatsHead.innerHTML = "";
    numStatsBody.innerHTML = "";

    if (numCols.length === 0) {
      numStatsBody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No numerical columns found in this dataset.</td></tr>`;
    } else {
      const headTr = document.createElement("tr");
      headTr.innerHTML = `<th>Feature</th><th>Count</th><th>Mean</th><th>Std Dev</th><th>Min</th><th>25% (Q1)</th><th>50% (Median)</th><th>75% (Q3)</th><th>Max</th>`;
      numStatsHead.appendChild(headTr);

      numCols.forEach((col) => {
        const s = numData[col] || {};
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="font-weight: 600;">${escapeHtml(col)}</td>
          <td>${s.count !== null ? Number(s.count).toLocaleString() : "-"}</td>
          <td>${s.mean !== null ? s.mean : "-"}</td>
          <td>${s.std !== null ? s.std : "-"}</td>
          <td>${s.min !== null ? s.min : "-"}</td>
          <td>${s["25%"] !== null ? s["25%"] : "-"}</td>
          <td>${s["50%"] !== null ? s["50%"] : "-"}</td>
          <td>${s["75%"] !== null ? s["75%"] : "-"}</td>
          <td>${s.max !== null ? s.max : "-"}</td>
        `;
        numStatsBody.appendChild(tr);
      });
    }
  }

  if (catStatsHead && catStatsBody) {
    catStatsHead.innerHTML = "";
    catStatsBody.innerHTML = "";

    if (catCols.length === 0) {
      catStatsBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No categorical columns found in this dataset.</td></tr>`;
    } else {
      const headTr = document.createElement("tr");
      headTr.innerHTML = `<th>Feature</th><th>Non-Null Count</th><th>Unique Count</th><th>Top Frequent Value</th><th>Frequency</th>`;
      catStatsHead.appendChild(headTr);

      catCols.forEach((col) => {
        const s = catData[col] || {};
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="font-weight: 600;">${escapeHtml(col)}</td>
          <td>${s.count !== null ? Number(s.count).toLocaleString() : "-"}</td>
          <td>${s.unique !== null ? Number(s.unique).toLocaleString() : "-"}</td>
          <td><strong>${s.top !== null ? escapeHtml(String(s.top)) : "-"}</strong></td>
          <td>${s.freq !== null ? Number(s.freq).toLocaleString() : "-"}</td>
        `;
        catStatsBody.appendChild(tr);
      });
    }
  }
}

if (btnTabNumStats && btnTabCatStats) {
  btnTabNumStats.addEventListener("click", () => {
    btnTabNumStats.classList.add("active");
    btnTabCatStats.classList.remove("active");
    if (numericalStatsContainer) numericalStatsContainer.style.display = "block";
    if (categoricalStatsContainer) categoricalStatsContainer.style.display = "none";
  });

  btnTabCatStats.addEventListener("click", () => {
    btnTabCatStats.classList.add("active");
    btnTabNumStats.classList.remove("active");
    if (numericalStatsContainer) numericalStatsContainer.style.display = "none";
    if (categoricalStatsContainer) categoricalStatsContainer.style.display = "block";
  });
}

function renderMissingValuesTable(missing) {
  if (!missingTableBody) return;
  missingTableBody.innerHTML = "";

  const cols = missing.columns || [];
  if (cols.length === 0) {
    missingTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center;">No columns evaluated.</td></tr>`;
    return;
  }

  cols.forEach((colInfo) => {
    const tr = document.createElement("tr");
    const pct = colInfo.missing_percentage || 0;
    const barColor = pct === 0 ? "var(--status-green)" : (pct > 20 ? "var(--status-red)" : "var(--accent-blue)");

    tr.innerHTML = `
      <td style="font-weight: 600;">${escapeHtml(colInfo.column)}</td>
      <td>${colInfo.missing_count.toLocaleString()}</td>
      <td><strong>${pct}%</strong></td>
      <td>
        <div style="background: var(--border-color); border-radius: 4px; height: 8px; width: 100%; overflow: hidden;">
          <div class="bar-fill-mini" style="width: ${Math.min(100, pct)}%; background-color: ${barColor};"></div>
        </div>
      </td>
    `;
    missingTableBody.appendChild(tr);
  });
}

function renderDuplicatesAndProfiles(duplicates, colAnalysis) {
  if (duplicateStatusBanner && dupBannerIcon && dupBannerTitle && dupBannerDesc) {
    if (duplicates.has_duplicates) {
      duplicateStatusBanner.className = "dup-banner has-dup";
      dupBannerIcon.innerHTML = "&#9888;";
      dupBannerTitle.textContent = `${duplicates.duplicate_count.toLocaleString()} Duplicate Rows Detected (${duplicates.duplicate_percentage}%)`;
      dupBannerDesc.textContent = "Data integrity note: duplicates are reported and preserved in accordance with standard EDA practices.";
    } else {
      duplicateStatusBanner.className = "dup-banner";
      dupBannerIcon.innerHTML = "&#10003;";
      dupBannerTitle.textContent = "Zero Duplicate Records (100% Unique)";
      dupBannerDesc.textContent = "Every observation in this dataset represents a distinct row.";
    }
  }

  if (columnAnalysisBody) {
    columnAnalysisBody.innerHTML = "";
    (colAnalysis || []).forEach((c) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight: 600;">${escapeHtml(c.column)}</td>
        <td><span class="type-pill">${escapeHtml(c.data_type)}</span></td>
        <td>${c.unique_count.toLocaleString()}</td>
        <td>${c.unique_percentage}%</td>
      `;
      columnAnalysisBody.appendChild(tr);
    });
  }
}

function renderOutliersTable(outliers) {
  if (!outliersTableBody) return;
  outliersTableBody.innerHTML = "";

  const cols = outliers.columns || [];
  if (cols.length === 0) {
    outliersTableBody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No numerical features available for outlier detection.</td></tr>`;
    return;
  }

  cols.forEach((item) => {
    const tr = document.createElement("tr");
    const boundsStr = item.lower_bound !== null && item.upper_bound !== null
      ? `[${item.lower_bound}, ${item.upper_bound}]`
      : "-";

    let samplesHtml = '<span class="text-muted">None</span>';
    if (item.sample_outliers && item.sample_outliers.length > 0) {
      const allSamples = item.sample_outliers;
      const visibleSamples = allSamples.slice(0, 10);
      const remaining = allSamples.length - visibleSamples.length;

      let tags = visibleSamples.map(val => `<span class="outlier-tag" title="Outlier value: ${escapeHtml(String(val))}">${escapeHtml(String(val))}</span>`).join("");
      if (remaining > 0) {
        tags += `<span class="outlier-tag-more" title="Additional outliers: ${escapeHtml(allSamples.slice(10).join(', '))}">+${remaining} more</span>`;
      }
      samplesHtml = `<div class="outliers-samples-wrap">${tags}</div>`;
    }

    const pct = item.outlier_percentage || 0;
    const highlightClass = item.outlier_count > 0 ? "style='font-weight: 700; color: var(--status-red);'" : "";

    tr.innerHTML = `
      <td style="font-weight: 600;">${escapeHtml(item.column)}</td>
      <td>${item.q1 !== null ? item.q1 : "-"}</td>
      <td>${item.q3 !== null ? item.q3 : "-"}</td>
      <td>${item.iqr !== null ? item.iqr : "-"}</td>
      <td><code>${boundsStr}</code></td>
      <td ${highlightClass}>${item.outlier_count.toLocaleString()}</td>
      <td ${highlightClass}>${pct}%</td>
      <td class="outliers-samples-td">${samplesHtml}</td>
    `;
    outliersTableBody.appendChild(tr);
  });
}

function renderCorrelationMatrix(correlation) {
  if (!correlationHead || !correlationBody) return;
  correlationHead.innerHTML = "";
  correlationBody.innerHTML = "";

  const numCols = correlation.numerical_columns || [];
  const matrix = correlation.matrix || {};

  if (numCols.length < 2) {
    if (correlationSubtitle) {
      correlationSubtitle.textContent = correlation.message || "At least 2 numerical columns are required for correlation analysis.";
    }
    correlationBody.innerHTML = `<tr><td colspan="2" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Insufficient numerical features for pairwise correlation.</td></tr>`;
    if (topCorrelationsBadges) topCorrelationsBadges.innerHTML = "<span class='text-muted'>None available</span>";
    return;
  }

  if (correlationSubtitle) {
    correlationSubtitle.textContent = `Pairwise Pearson correlation coefficients across ${numCols.length} numerical features.`;
  }

  const headTr = document.createElement("tr");
  const cornerTh = document.createElement("th");
  cornerTh.textContent = "";
  headTr.appendChild(cornerTh);

  numCols.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    headTr.appendChild(th);
  });
  correlationHead.appendChild(headTr);

  numCols.forEach((rowCol) => {
    const tr = document.createElement("tr");
    const rowHeader = document.createElement("th");
    rowHeader.textContent = rowCol;
    tr.appendChild(rowHeader);

    numCols.forEach((colCol) => {
      const td = document.createElement("td");
      td.className = "corr-cell";

      const r = matrix[rowCol] ? matrix[rowCol][colCol] : null;

      if (r === null || r === undefined) {
        td.textContent = "N/A";
        td.style.backgroundColor = "var(--bg-secondary)";
        td.style.color = "var(--text-muted)";
      } else {
        td.textContent = Number(r).toFixed(2);
        td.title = `Correlation(${rowCol}, ${colCol}) = ${r}`;

        if (rowCol === colCol) {
          td.style.backgroundColor = "var(--accent-blue-light)";
          td.style.color = "var(--accent-blue)";
          td.style.fontWeight = "700";
        } else {
          const absR = Math.abs(r);
          if (r > 0) {
            td.style.backgroundColor = `rgba(37, 99, 235, ${Math.max(0.08, absR * 0.4)})`;
            td.style.color = absR > 0.6 ? "#1e3a8a" : "var(--text-primary)";
          } else {
            td.style.backgroundColor = `rgba(220, 38, 38, ${Math.max(0.08, absR * 0.35)})`;
            td.style.color = absR > 0.6 ? "#7f1d1d" : "var(--text-primary)";
          }
        }
      }
      tr.appendChild(td);
    });
    correlationBody.appendChild(tr);
  });

  if (topCorrelationsBadges) {
    topCorrelationsBadges.innerHTML = "";
    const topPairs = correlation.top_correlations || [];

    if (topPairs.length === 0) {
      topCorrelationsBadges.innerHTML = "<span class='text-muted'>No non-zero correlations identified.</span>";
    } else {
      topPairs.slice(0, 6).forEach((pair) => {
        const badge = document.createElement("div");
        badge.className = "corr-badge";
        const sign = pair.correlation >= 0 ? "+" : "";
        badge.innerHTML = `
          <span>${escapeHtml(pair.col1)} &harr; ${escapeHtml(pair.col2)}:</span>
          <strong>${sign}${pair.correlation}</strong>
        `;
        topCorrelationsBadges.appendChild(badge);
      });
    }
  }
}

function setupDistributionVisualizer(distributions, colAnalysis) {
  if (!selectDistColumn) return;
  selectDistColumn.innerHTML = "";

  const numDists = distributions.numerical || {};
  const catDists = distributions.categorical || {};

  const numKeys = Object.keys(numDists);
  const catKeys = Object.keys(catDists);

  if (numKeys.length === 0 && catKeys.length === 0) {
    selectDistColumn.innerHTML = `<option value="">No features available</option>`;
    if (chartContainer) {
      chartContainer.innerHTML = "<p class='text-muted'>No distribution data available.</p>";
    }
    return;
  }

  if (numKeys.length > 0) {
    const numGroup = document.createElement("optgroup");
    numGroup.label = "Numerical Features (Histograms)";
    numKeys.forEach((k) => {
      const opt = document.createElement("option");
      opt.value = `num:${k}`;
      opt.textContent = `${k} [Numeric]`;
      numGroup.appendChild(opt);
    });
    selectDistColumn.appendChild(numGroup);
  }

  if (catKeys.length > 0) {
    const catGroup = document.createElement("optgroup");
    catGroup.label = "Categorical Features (Bar Frequencies)";
    catKeys.forEach((k) => {
      const opt = document.createElement("option");
      opt.value = `cat:${k}`;
      opt.textContent = `${k} [Categorical]`;
      catGroup.appendChild(opt);
    });
    selectDistColumn.appendChild(catGroup);
  }

  selectDistColumn.onchange = () => {
    renderSelectedDistribution(selectDistColumn.value, distributions);
  };

  if (selectDistColumn.options.length > 0) {
    selectDistColumn.selectedIndex = 0;
    renderSelectedDistribution(selectDistColumn.value, distributions);
  }
}

function renderSelectedDistribution(selectedVal, distributions) {
  if (!selectedVal) return;
  const [type, colName] = selectedVal.split(":");

  if (type === "num") {
    const distData = distributions.numerical[colName];
    if (!distData) return;

    if (distMetaBar) {
      distMetaBar.innerHTML = `
        <div class="dist-meta-card"><span class="dist-meta-label">Feature</span><span class="dist-meta-val">${escapeHtml(colName)}</span></div>
        <div class="dist-meta-card"><span class="dist-meta-label">Minimum</span><span class="dist-meta-val">${distData.min !== null ? distData.min : "-"}</span></div>
        <div class="dist-meta-card"><span class="dist-meta-label">Maximum</span><span class="dist-meta-val">${distData.max !== null ? distData.max : "-"}</span></div>
        <div class="dist-meta-card"><span class="dist-meta-label">Mean</span><span class="dist-meta-val">${distData.mean !== null ? distData.mean : "-"}</span></div>
        <div class="dist-meta-card"><span class="dist-meta-label">Median</span><span class="dist-meta-val">${distData.median !== null ? distData.median : "-"}</span></div>
        <div class="dist-meta-card"><span class="dist-meta-label">Std Dev</span><span class="dist-meta-val">${distData.std !== null ? distData.std : "-"}</span></div>
      `;
    }

    renderSvgHistogram(distData.bins || []);
  } else if (type === "cat") {
    const categories = distributions.categorical[colName] || [];

    if (distMetaBar) {
      const totalFreq = categories.reduce((acc, cur) => acc + (cur.count || 0), 0);
      distMetaBar.innerHTML = `
        <div class="dist-meta-card"><span class="dist-meta-label">Feature</span><span class="dist-meta-val">${escapeHtml(colName)}</span></div>
        <div class="dist-meta-card"><span class="dist-meta-label">Categories Counted</span><span class="dist-meta-val">${categories.length}</span></div>
        <div class="dist-meta-card"><span class="dist-meta-label">Total Observations</span><span class="dist-meta-val">${totalFreq.toLocaleString()}</span></div>
      `;
    }

    renderSvgBarChart(categories);
  }
}

function formatHistNum(val) {
  if (val === null || val === undefined || isNaN(val)) return "-";
  const n = Number(val);
  if (Math.abs(n) >= 1e6) {
    return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
  }
  if (Math.abs(n) >= 1e4) {
    return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "k";
  }
  if (Number.isInteger(n)) {
    return n.toLocaleString();
  }
  return parseFloat(n.toFixed(2)).toLocaleString();
}

function renderSvgHistogram(bins) {
  if (!chartContainer) return;
  chartContainer.innerHTML = "";

  if (bins.length === 0) {
    chartContainer.innerHTML = "<p class='text-muted' style='padding: 1.5rem; text-align: center;'>No histogram bins available for this column.</p>";
    return;
  }

  const svgWidth = 860;
  const svgHeight = 280;
  const padLeft = 65;
  const padRight = 35;
  const padTop = 30;
  const padBottom = 65;

  const chartW = svgWidth - padLeft - padRight;
  const chartH = svgHeight - padTop - padBottom;

  const maxCount = Math.max(...bins.map((b) => b.count), 1);
  const barW = chartW / bins.length;

  let barsSvg = "";
  let labelsSvg = "";

  // Horizontal gridlines & Y-axis labels
  let gridSvg = `
    <line x1="${padLeft}" y1="${padTop}" x2="${svgWidth - padRight}" y2="${padTop}" class="svg-grid-line" />
    <line x1="${padLeft}" y1="${padTop + chartH / 2}" x2="${svgWidth - padRight}" y2="${padTop + chartH / 2}" class="svg-grid-line" />
    <line x1="${padLeft}" y1="${padTop + chartH}" x2="${svgWidth - padRight}" y2="${padTop + chartH}" stroke="var(--border-color)" stroke-width="1.5" />
    <text x="${padLeft - 10}" y="${padTop + 4}" class="svg-text" text-anchor="end">${maxCount.toLocaleString()}</text>
    <text x="${padLeft - 10}" y="${padTop + chartH / 2 + 4}" class="svg-text" text-anchor="end">${Math.round(maxCount / 2).toLocaleString()}</text>
    <text x="${padLeft - 10}" y="${padTop + chartH + 4}" class="svg-text" text-anchor="end">0</text>
  `;

  // Determine tick display to avoid label collisions on high bin counts
  const step = bins.length > 8 ? 2 : 1;
  const showIndices = new Set();
  for (let i = 0; i < bins.length; i += step) {
    showIndices.add(i);
  }
  showIndices.add(bins.length - 1); // Always include the last bin
  if (bins.length > 5 && showIndices.has(bins.length - 2) && showIndices.has(bins.length - 1)) {
    showIndices.delete(bins.length - 2); // Prevent collision between last two adjacent labels
  }

  bins.forEach((b, i) => {
    const h = (b.count / maxCount) * chartH;
    const x = padLeft + i * barW + 2;
    const y = padTop + chartH - h;
    const w = Math.max(2, barW - 4);

    const shortLabel = `${formatHistNum(b.bin_start)} – ${formatHistNum(b.bin_end)}`;
    const fullTooltip = `Bin Range: [${b.bin_start} to ${b.bin_end}]\nFrequency Count: ${b.count.toLocaleString()}`;

    barsSvg += `
      <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3" class="svg-bar">
        <title>${escapeHtml(fullTooltip)}</title>
      </rect>
    `;

    if (b.count > 0) {
      barsSvg += `
        <text x="${x + w / 2}" y="${y - 6}" class="svg-bar-count" text-anchor="middle">
          ${b.count.toLocaleString()}
          <title>${escapeHtml(fullTooltip)}</title>
        </text>
      `;
    }

    // Tick mark on baseline
    gridSvg += `
      <line x1="${x + w / 2}" y1="${padTop + chartH}" x2="${x + w / 2}" y2="${padTop + chartH + 5}" stroke="var(--border-color)" stroke-width="1" />
    `;

    if (showIndices.has(i)) {
      labelsSvg += `
        <text x="${x + w / 2}" y="${padTop + chartH + 14}" transform="rotate(-30, ${x + w / 2}, ${padTop + chartH + 14})" text-anchor="end" class="svg-text" font-size="11px">
          ${escapeHtml(shortLabel)}
          <title>${escapeHtml(fullTooltip)}</title>
        </text>
      `;
    }
  });

  chartContainer.innerHTML = `
    <svg viewBox="0 0 ${svgWidth} ${svgHeight}" class="svg-chart" style="width: 100%; height: ${svgHeight}px; max-height: 320px;" preserveAspectRatio="xMidYMid meet">
      ${gridSvg}
      ${barsSvg}
      ${labelsSvg}
    </svg>
  `;
}

function renderSvgBarChart(categories) {
  if (!chartContainer) return;
  chartContainer.innerHTML = "";

  if (categories.length === 0) {
    chartContainer.innerHTML = "<p class='text-muted' style='padding: 1.5rem; text-align: center;'>No categories available for this feature.</p>";
    return;
  }

  const svgWidth = 920;
  const rowHeight = 36;
  const barH = 22;
  const padLeft = 210;
  const padRight = 150;
  const padTop = 20;
  const padBottom = 20;

  const svgHeight = padTop + categories.length * rowHeight + padBottom;
  const chartW = svgWidth - padLeft - padRight;
  const maxCount = Math.max(...categories.map((c) => c.count), 1);

  let itemsSvg = "";

  // Vertical baseline separating labels from bars
  itemsSvg += `
    <line x1="${padLeft}" y1="${padTop - 5}" x2="${padLeft}" y2="${svgHeight - padBottom + 5}" stroke="var(--border-color)" stroke-width="1.5" />
  `;

  categories.forEach((cat, i) => {
    const y = padTop + i * rowHeight;
    const barY = y + (rowHeight - barH) / 2;
    const textY = y + rowHeight / 2 + 4;
    const w = (cat.count / maxCount) * chartW;

    // Truncate long category labels for clean presentation, preserving full name in tooltip
    let rawName = String(cat.category || "(Missing)");
    let displayLabel = rawName;
    if (displayLabel.length > 24) {
      displayLabel = displayLabel.slice(0, 22) + "...";
    }

    const tooltipText = `${rawName}: ${cat.count.toLocaleString()} occurrences (${cat.percentage}%)`;

    itemsSvg += `
      <text x="${padLeft - 12}" y="${textY}" class="svg-cat-label" text-anchor="end">
        ${escapeHtml(displayLabel)}
        <title>${escapeHtml(tooltipText)}</title>
      </text>
      <rect x="${padLeft}" y="${barY}" width="${Math.max(4, w)}" height="${barH}" rx="4" class="svg-bar">
        <title>${escapeHtml(tooltipText)}</title>
      </rect>
      <text x="${padLeft + w + 10}" y="${textY}" class="svg-cat-value" text-anchor="start">
        ${cat.count.toLocaleString()} (${cat.percentage}%)
        <title>${escapeHtml(tooltipText)}</title>
      </text>
    `;
  });

  chartContainer.innerHTML = `
    <svg viewBox="0 0 ${svgWidth} ${svgHeight}" class="svg-chart" style="width: 100%; height: ${svgHeight}px;" preserveAspectRatio="xMinYMid meet">
      ${itemsSvg}
    </svg>
  `;
}

/* -------------------------------------------------------------
 * 6. Phase 4: Data Cleaning Studio Implementation
 * ------------------------------------------------------------- */
function populateCleaningDropdowns(columns, dataTypes) {
  const isNumeric = (col) => {
    const t = (dataTypes[col] || "").toLowerCase();
    return t.includes("int") || t.includes("float") || t.includes("num");
  };

  const populateSelect = (selectEl, cols, includeAllOption = false) => {
    if (!selectEl) return;
    selectEl.innerHTML = "";
    if (includeAllOption) {
      const optAll = document.createElement("option");
      optAll.value = "all";
      optAll.textContent = "All Columns (Any)";
      selectEl.appendChild(optAll);
    }
    cols.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = `${c} (${dataTypes[c] || "type"})`;
      selectEl.appendChild(opt);
    });
  };

  const numCols = columns.filter(isNumeric);
  const catCols = columns.filter((c) => !isNumeric(c));

  // 1. Missing Values Target
  populateSelect(selectMissingCol, columns, true);

  // 2. Type Casting
  populateSelect(selectTypeCol, columns);

  // 3. Outlier Treatment (numerical)
  populateSelect(selectOutlierCol, numCols.length > 0 ? numCols : columns);

  // 4. Categorical Encoding (categorical preferred, fallback all)
  populateSelect(selectEncodeCol, catCols.length > 0 ? catCols : columns);

  // 5. Numerical Scaling (numerical preferred, fallback all)
  populateSelect(selectScaleCol, numCols.length > 0 ? numCols : columns);

  // 6. Rename
  populateSelect(selectRenameCol, columns);

  // 7. Drop
  populateSelect(selectDropCol, columns);
}

// Strategy change event for custom missing value input
if (selectMissingStrategy && groupCustomMissingVal) {
  selectMissingStrategy.addEventListener("change", () => {
    groupCustomMissingVal.style.display = selectMissingStrategy.value === "custom" ? "flex" : "none";
  });
}

// Queue Management
function addCleaningOperation(operationObj, label) {
  queuedCleaningOperations.push({ ...operationObj, _displayLabel: label });
  updatePipelineQueueUI();
}

function removeCleaningOperation(index) {
  queuedCleaningOperations.splice(index, 1);
  updatePipelineQueueUI();
}

function clearCleaningPipeline() {
  queuedCleaningOperations = [];
  updatePipelineQueueUI();
  if (cleanPreviewContainer) cleanPreviewContainer.style.display = "none";
}

function updatePipelineQueueUI() {
  const count = queuedCleaningOperations.length + (chkDropDuplicates && chkDropDuplicates.checked ? 1 : 0);
  if (pipelineCountBadge) {
    pipelineCountBadge.textContent = `${count} Operation${count === 1 ? "" : "s"}`;
  }

  if (!pipelineList) return;
  pipelineList.innerHTML = "";

  if (chkDropDuplicates && chkDropDuplicates.checked) {
    const item = document.createElement("div");
    item.className = "pipeline-item";
    item.innerHTML = `
      <span class="pipeline-item-desc">&#128465; Remove Duplicate Rows (First Occurrence Kept)</span>
      <span style="font-size: 0.75rem; color: var(--text-muted);">(Toggle)</span>
    `;
    pipelineList.appendChild(item);
  }

  if (queuedCleaningOperations.length === 0 && (!chkDropDuplicates || !chkDropDuplicates.checked)) {
    pipelineList.innerHTML = `
      <div class="empty-pipeline-msg">
        No transformation steps added yet. Add rules on the left, then click "Preview Changes".
      </div>
    `;
    return;
  }

  queuedCleaningOperations.forEach((op, idx) => {
    const item = document.createElement("div");
    item.className = "pipeline-item";
    item.innerHTML = `
      <span class="pipeline-item-desc">${escapeHtml(op._displayLabel || op.type)}</span>
      <button class="pipeline-remove-btn" type="button" title="Remove step">&times;</button>
    `;
    item.querySelector(".pipeline-remove-btn").addEventListener("click", () => {
      removeCleaningOperation(idx);
    });
    pipelineList.appendChild(item);
  });
}

if (chkDropDuplicates) {
  chkDropDuplicates.addEventListener("change", () => {
    updatePipelineQueueUI();
  });
}

// Add Operation Listeners
if (btnAddMissingOp) {
  btnAddMissingOp.addEventListener("click", () => {
    const col = selectMissingCol ? selectMissingCol.value : "all";
    const strat = selectMissingStrategy ? selectMissingStrategy.value : "drop_rows";
    let desc = "";

    const op = { type: "fill_missing", column: col, strategy: strat };
    if (strat === "drop_rows") {
      op.type = "drop_missing";
      desc = `Drop missing rows in '${col}'`;
    } else if (strat === "custom") {
      const val = inputCustomMissingVal ? inputCustomMissingVal.value.trim() : "";
      if (!val) {
        showError("Please specify a custom fill value.");
        return;
      }
      op.fill_value = val;
      desc = `Fill missing in '${col}' with '${val}'`;
    } else {
      desc = `Fill missing in '${col}' with ${strat}`;
    }

    addCleaningOperation(op, desc);
  });
}

if (btnAddTypeOp) {
  btnAddTypeOp.addEventListener("click", () => {
    const col = selectTypeCol ? selectTypeCol.value : "";
    const target = selectTargetType ? selectTargetType.value : "string";
    if (!col) return;
    addCleaningOperation({ type: "convert_type", column: col, target_type: target }, `Cast '${col}' to ${target}`);
  });
}

if (btnAddOutlierOp) {
  btnAddOutlierOp.addEventListener("click", () => {
    const col = selectOutlierCol ? selectOutlierCol.value : "";
    const action = selectOutlierAction ? selectOutlierAction.value : "cap";
    if (!col) return;
    const desc = action === "cap" ? `Cap outliers in '${col}' to IQR bounds` : `Remove outlier rows from '${col}'`;
    addCleaningOperation({ type: "handle_outliers", column: col, action }, desc);
  });
}

if (btnAddEncodeOp) {
  btnAddEncodeOp.addEventListener("click", () => {
    const col = selectEncodeCol ? selectEncodeCol.value : "";
    const method = selectEncodeMethod ? selectEncodeMethod.value : "label";
    if (!col) return;
    const desc = method === "label" ? `Label Encode '${col}'` : `One-Hot Encode '${col}'`;
    addCleaningOperation({ type: "encode_column", column: col, method }, desc);
  });
}

if (btnAddScaleOp) {
  btnAddScaleOp.addEventListener("click", () => {
    const col = selectScaleCol ? selectScaleCol.value : "";
    const method = selectScaleMethod ? selectScaleMethod.value : "min_max";
    if (!col) return;
    const desc = method === "min_max" ? `Min-Max scale [0, 1] on '${col}'` : `Standardize Z-score on '${col}'`;
    addCleaningOperation({ type: "scale_column", column: col, method }, desc);
  });
}

if (btnAddRenameOp) {
  btnAddRenameOp.addEventListener("click", () => {
    const col = selectRenameCol ? selectRenameCol.value : "";
    const newName = inputNewColName ? inputNewColName.value.trim() : "";
    if (!col) return;
    if (!newName) {
      showError("Please enter a new column name.");
      return;
    }
    addCleaningOperation({ type: "rename_column", old_name: col, new_name: newName }, `Rename '${col}' &rarr; '${newName}'`);
    if (inputNewColName) inputNewColName.value = "";
  });
}

if (btnAddDropOp) {
  btnAddDropOp.addEventListener("click", () => {
    const col = selectDropCol ? selectDropCol.value : "";
    if (!col) return;
    addCleaningOperation({ type: "drop_column", column: col }, `Remove column '${col}'`);
  });
}

if (btnClearPipeline) {
  btnClearPipeline.addEventListener("click", () => {
    clearCleaningPipeline();
  });
}

function collectActiveOperations() {
  const ops = [];
  if (chkDropDuplicates && chkDropDuplicates.checked) {
    ops.push({ type: "drop_duplicates", keep: "first" });
  }
  queuedCleaningOperations.forEach((op) => {
    const cleanOp = { ...op };
    delete cleanOp._displayLabel;
    ops.push(cleanOp);
  });
  return ops;
}

/* --- Preview Cleaning Operations --- */
async function previewCleaningChanges() {
  const fileToClean = currentUploadedFile || stagedFile;
  if (!fileToClean) {
    showError("No active dataset to preview. Please upload a file first.");
    return;
  }

  const baseUrl = checkBackendConfigured();
  if (!baseUrl) return;

  const ops = collectActiveOperations();
  if (ops.length === 0) {
    showError("No cleaning operations configured. Add at least one cleaning or duplicate rule.");
    return;
  }

  dismissError();
  if (cleanLoading) cleanLoading.style.display = "flex";
  if (btnPreviewClean) btnPreviewClean.disabled = true;

  const formData = new FormData();
  formData.append("file", fileToClean);
  formData.append("operations", JSON.stringify(ops));

  try {
    const response = await fetch(`${baseUrl}/api/clean/preview`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      const errorMsg = data && data.detail ? data.detail : `Server error (${response.status}): ${response.statusText}`;
      throw new Error(errorMsg);
    }

    renderCleanPreview(data);

    if (cleanLoading) cleanLoading.style.display = "none";
    if (cleanPreviewContainer) {
      cleanPreviewContainer.style.display = "block";
      cleanPreviewContainer.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (error) {
    showError(error.message || "Failed to preview cleaning operations.");
    if (cleanLoading) cleanLoading.style.display = "none";
  } finally {
    if (btnPreviewClean) btnPreviewClean.disabled = false;
  }
}

function renderCleanPreview(data) {
  const orig = data.original_summary || {};
  const clean = data.cleaned_summary || {};
  const diff = data.diff_summary || {};

  if (diffRows) {
    const rDelta = diff.rows_delta || 0;
    const sign = rDelta > 0 ? "+" : "";
    diffRows.textContent = `${orig.row_count} → ${clean.row_count}`;
    if (diffRowsSub) diffRowsSub.textContent = `Delta: ${sign}${rDelta} rows`;
  }

  if (diffCols) {
    const cDelta = diff.columns_delta || 0;
    const sign = cDelta > 0 ? "+" : "";
    diffCols.textContent = `${orig.column_count} → ${clean.column_count}`;
    if (diffColsSub) diffColsSub.textContent = `Delta: ${sign}${cDelta} columns`;
  }

  if (diffOpsCount) {
    diffOpsCount.textContent = `${(data.operations_applied || []).length} Applied`;
  }

  if (operationsLogList) {
    operationsLogList.innerHTML = "";
    (data.operations_applied || []).forEach((logText) => {
      const li = document.createElement("li");
      li.className = "operations-log-item";
      li.textContent = logText;
      operationsLogList.appendChild(li);
    });
  }

  // Render Cleaned Preview Table (After)
  renderTablePreview(clean, cleanedTableHead, cleanedTableBody);

  // Render Original Preview Table (Before)
  renderTablePreview(orig, originalTableHead, originalTableBody);
}

function renderTablePreview(summary, theadEl, tbodyEl) {
  if (!theadEl || !tbodyEl) return;
  theadEl.innerHTML = "";
  tbodyEl.innerHTML = "";

  const cols = summary.columns || [];
  const headTr = document.createElement("tr");

  const idxTh = document.createElement("th");
  idxTh.className = "row-index-cell";
  idxTh.textContent = "#";
  headTr.appendChild(idxTh);

  cols.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    headTr.appendChild(th);
  });
  theadEl.appendChild(headTr);

  const rows = summary.preview || [];
  rows.forEach((r, idx) => {
    const tr = document.createElement("tr");
    const idxTd = document.createElement("td");
    idxTd.className = "row-index-cell";
    idxTd.textContent = idx + 1;
    tr.appendChild(idxTd);

    cols.forEach((c) => {
      const td = document.createElement("td");
      const v = r[c];
      if (v === null || v === undefined) {
        td.innerHTML = `<span class="null-pill">null</span>`;
      } else {
        td.textContent = String(v);
      }
      tr.appendChild(td);
    });
    tbodyEl.appendChild(tr);
  });
}

// Clean vs Original Tab Switching
if (btnTabCleanedPreview && btnTabOriginalPreview) {
  btnTabCleanedPreview.addEventListener("click", () => {
    btnTabCleanedPreview.classList.add("active");
    btnTabOriginalPreview.classList.remove("active");
    if (cleanedTableContainer) cleanedTableContainer.style.display = "block";
    if (originalTableContainer) originalTableContainer.style.display = "none";
  });

  btnTabOriginalPreview.addEventListener("click", () => {
    btnTabOriginalPreview.classList.add("active");
    btnTabCleanedPreview.classList.remove("active");
    if (cleanedTableContainer) cleanedTableContainer.style.display = "none";
    if (originalTableContainer) originalTableContainer.style.display = "block";
  });
}

/* --- Apply Changes & Download --- */
async function applyCleanedDataset() {
  const fileToClean = currentUploadedFile || stagedFile;
  if (!fileToClean) return;

  const baseUrl = checkBackendConfigured();
  if (!baseUrl) return;

  const ops = collectActiveOperations();
  if (btnApplyCleaned) btnApplyCleaned.disabled = true;

  const formData = new FormData();
  formData.append("file", fileToClean);
  formData.append("operations", JSON.stringify(ops));
  formData.append("format", "csv");

  try {
    const response = await fetch(`${baseUrl}/api/clean/download`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Failed to commit cleaned dataset.");
    }

    const blob = await response.blob();
    const newName = fileToClean.name.startsWith("cleaned_") ? fileToClean.name : `cleaned_${fileToClean.name}`;
    currentUploadedFile = new File([blob], newName, { type: "text/csv" });

    // Upload & inspect new in-memory file so all metrics, schema, and tables refresh!
    stagedFile = currentUploadedFile;
    await uploadAndInspectDataset();

    clearCleaningPipeline();
    if (cleanPreviewContainer) cleanPreviewContainer.style.display = "none";

    alert("Cleaned dataset applied successfully as the active working dataset! You can now re-run Automated EDA or download it.");
  } catch (error) {
    showError(error.message || "Could not apply cleaned dataset.");
  } finally {
    if (btnApplyCleaned) btnApplyCleaned.disabled = false;
  }
}

async function downloadDatasetFile(format) {
  const baseUrl = checkBackendConfigured();
  if (!baseUrl) return;

  const fileToClean = currentUploadedFile || stagedFile;
  if (!fileToClean) {
    showError("No active dataset to download.");
    return;
  }

  const ops = collectActiveOperations();
  const formData = new FormData();
  formData.append("file", fileToClean);
  formData.append("operations", JSON.stringify(ops));
  formData.append("format", format);

  try {
    const response = await fetch(`${baseUrl}/api/clean/download`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || `Download failed (${response.status})`);
    }

    const blob = await response.blob();

    // Cache cleaned dataset for visualization studio
    const baseName = fileToClean.name.replace(/\.[^/.]+$/, "");
    const ext = format === "xlsx" ? "xlsx" : (format === "json" ? "json" : "csv");
    const mime = format === "xlsx"
      ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      : (format === "json" ? "application/json" : "text/csv");
    const downloadFileName = `cleaned_${baseName}.${ext}`;
    cleanedDatasetFile = new File([blob], downloadFileName, { type: mime });
    cleanedDatasetMeta = {
      filename: downloadFileName,
      row_count: activeDatasetColumns.length > 0 ? (statRowCount ? parseInt(statRowCount.textContent.replace(/,/g, "")) || 0 : 0) : 0,
      column_count: activeDatasetColumns.length,
      columns: [...activeDatasetColumns],
      data_types: { ...activeDatasetTypes },
    };
    updateVisDatasetSwitcherUI();
    updateReportDatasetSwitcherUI();

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadFileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    showError(error.message || "Failed to download cleaned dataset.");
  }
}

/* -------------------------------------------------------------
 * 7. Global Event Bindings
 * ------------------------------------------------------------- */
if (btnUpload) {
  btnUpload.addEventListener("click", () => {
    uploadAndInspectDataset();
  });
}

if (btnRunAnalysis) {
  btnRunAnalysis.addEventListener("click", () => {
    runAutomatedAnalysis();
  });
}

if (btnOpenCleaningStudio) {
  btnOpenCleaningStudio.addEventListener("click", () => {
    if (cleaningStudioSection) {
      cleaningStudioSection.style.display = "block";
      cleaningStudioSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}

if (btnGoToCleanerFromEda) {
  btnGoToCleanerFromEda.addEventListener("click", () => {
    if (cleaningStudioSection) {
      cleaningStudioSection.style.display = "block";
      cleaningStudioSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}

if (btnScrollToPreview) {
  btnScrollToPreview.addEventListener("click", () => {
    const uploadSec = document.getElementById("resultsSection");
    if (uploadSec) uploadSec.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

if (btnPreviewClean) {
  btnPreviewClean.addEventListener("click", () => {
    previewCleaningChanges();
  });
}

if (btnApplyCleaned) {
  btnApplyCleaned.addEventListener("click", () => {
    applyCleanedDataset();
  });
}

if (btnDownloadCsv) {
  btnDownloadCsv.addEventListener("click", () => {
    downloadDatasetFile("csv");
  });
}

if (btnDownloadXlsx) {
  btnDownloadXlsx.addEventListener("click", () => {
    downloadDatasetFile("xlsx");
  });
}

if (btnDownloadJson) {
  btnDownloadJson.addEventListener("click", () => {
    downloadDatasetFile("json");
  });
}

if (btnUploadAnother) {
  btnUploadAnother.addEventListener("click", () => {
    resetStaging();
    if (resultsSection) resultsSection.style.display = "none";
    if (edaDashboardSection) edaDashboardSection.style.display = "none";
    if (cleaningStudioSection) cleaningStudioSection.style.display = "none";
    if (visualizationStudioSection) visualizationStudioSection.style.display = "none";
    const uploadCard = document.getElementById("uploadSection");
    if (uploadCard) uploadCard.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

if (btnScrollToTop) {
  btnScrollToTop.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

if (btnCheckHealth) {
  btnCheckHealth.addEventListener("click", () => {
    checkBackendHealth();
  });
}

/* -------------------------------------------------------------
 * 8. Phase 5: Interactive Data Visualization Studio
 * ------------------------------------------------------------- */

function getActiveDatasetFile() {
  if (activeVisSource === "cleaned" && cleanedDatasetFile) {
    return cleanedDatasetFile;
  }
  return originalDatasetFile || currentUploadedFile || stagedFile;
}

function getActiveDatasetMeta() {
  if (activeVisSource === "cleaned" && cleanedDatasetMeta) {
    return cleanedDatasetMeta;
  }
  return originalDatasetMeta || {
    columns: activeDatasetColumns,
    data_types: activeDatasetTypes,
    filename: (originalDatasetFile ? originalDatasetFile.name : (currentUploadedFile ? currentUploadedFile.name : "original_dataset.csv")),
    row_count: 0,
    column_count: activeDatasetColumns.length,
  };
}

function updateVisDatasetSwitcherUI() {
  if (!labelSourceOriginal || !labelSourceCleaned) return;

  if (originalDatasetMeta) {
    labelSourceOriginal.textContent = `Original (${originalDatasetMeta.filename}) • ${originalDatasetMeta.row_count} rows`;
  } else {
    labelSourceOriginal.textContent = "Original Dataset";
  }

  if (cleanedDatasetFile && cleanedDatasetMeta) {
    btnSourceCleaned.disabled = false;
    btnSourceCleaned.classList.remove("disabled");
    btnSourceCleaned.title = "Switch to Cleaned Dataset";
    labelSourceCleaned.textContent = `Cleaned (${cleanedDatasetMeta.filename}) • ${cleanedDatasetMeta.row_count} rows`;
  } else {
    btnSourceCleaned.disabled = true;
    btnSourceCleaned.classList.add("disabled");
    btnSourceCleaned.title = "Apply or download a cleaned dataset in Cleaning Studio first";
    labelSourceCleaned.textContent = "Cleaned Dataset (None)";
    if (activeVisSource === "cleaned") {
      activeVisSource = "original";
    }
  }

  if (activeVisSource === "original") {
    btnSourceOriginal.classList.add("active");
    btnSourceCleaned.classList.remove("active");
    if (activeSourceDetails) {
      const meta = originalDatasetMeta || {};
      activeSourceDetails.textContent = `${meta.filename || "Original"} (${meta.row_count || 0} rows, ${meta.column_count || 0} cols)`;
    }
  } else {
    btnSourceCleaned.classList.add("active");
    btnSourceOriginal.classList.remove("active");
    if (activeSourceDetails) {
      const meta = cleanedDatasetMeta || {};
      activeSourceDetails.textContent = `${meta.filename || "Cleaned"} (${meta.row_count || 0} rows, ${meta.column_count || 0} cols)`;
    }
  }
}

function isColumnNumericByName(colName) {
  if (!colName) return false;
  const meta = getActiveDatasetMeta();
  const types = meta.data_types || {};
  const t = String(types[colName] || "").toLowerCase();
  return (
    t.includes("int") ||
    t.includes("float") ||
    t.includes("double") ||
    t.includes("num") ||
    t.includes("decimal")
  );
}

function updateVisAggregationOptions() {
  if (!visAggregation) return;
  const ctype = visChartType ? visChartType.value : "bar";
  const yCol = visYCol ? visYCol.value : "";

  const optCount = visAggregation.querySelector('option[value="count"]');
  const optMean = visAggregation.querySelector('option[value="mean"]');
  const optSum = visAggregation.querySelector('option[value="sum"]');
  const optMedian = visAggregation.querySelector('option[value="median"]');

  if (!optCount || !optMean || !optSum || !optMedian) return;

  if (ctype === "bar" || ctype === "pie" || ctype === "donut") {
    if (!yCol) {
      optCount.disabled = false;
      optCount.textContent = "Count (Frequency)";
      optMean.disabled = true;
      optMean.textContent = "Mean (Numerical Y required)";
      optSum.disabled = true;
      optSum.textContent = "Sum (Numerical Y required)";
      optMedian.disabled = true;
      optMedian.textContent = "Median (Numerical Y required)";
      visAggregation.value = "count";
    } else if (!isColumnNumericByName(yCol)) {
      // Categorical Y: COUNT is the valid aggregation
      optCount.disabled = false;
      optCount.textContent = `Count (Frequency of ${yCol})`;
      optMean.disabled = true;
      optMean.textContent = "Mean (Numerical only)";
      optSum.disabled = true;
      optSum.textContent = "Sum (Numerical only)";
      optMedian.disabled = true;
      optMedian.textContent = "Median (Numerical only)";
      visAggregation.value = "count";
    } else {
      // Numerical Y: all aggregations supported
      optCount.disabled = false;
      optCount.textContent = "Count (Frequency)";
      optMean.disabled = false;
      optMean.textContent = "Mean (Average)";
      optSum.disabled = false;
      optSum.textContent = "Sum (Total)";
      optMedian.disabled = false;
      optMedian.textContent = "Median";
    }
  } else if (ctype === "line") {
    optCount.disabled = false;
    optCount.textContent = "Count";
    optMean.disabled = false;
    optMean.textContent = "Mean (Average)";
    optSum.disabled = false;
    optSum.textContent = "Sum (Total)";
    optMedian.disabled = false;
    optMedian.textContent = "Median";
    if (visAggregation.value === "count") {
      visAggregation.value = "mean";
    }
  }
}

function populateVisualizationDropdowns() {
  if (!visXCol || !visYCol) return;

  const meta = getActiveDatasetMeta();
  const cols = meta.columns || [];

  const currentX = visXCol.value;
  const currentY = visYCol.value;

  visXCol.innerHTML = '<option value="">-- Select Column --</option>';
  visYCol.innerHTML = '<option value="">-- None (Count only) --</option>';

  cols.forEach((col) => {
    const isNum = isColumnNumericByName(col);

    // X Option
    const optX = document.createElement("option");
    optX.value = col;
    optX.textContent = `${col} (${isNum ? "numeric" : "category"})`;
    visXCol.appendChild(optX);

    // Y Option
    const optY = document.createElement("option");
    optY.value = col;
    optY.textContent = `${col} (${isNum ? "numeric" : "category"})`;
    visYCol.appendChild(optY);
  });

  if (cols.includes(currentX)) visXCol.value = currentX;
  if (cols.includes(currentY)) visYCol.value = currentY;

  updateVisControlVisibility();
  updateVisAggregationOptions();
}

function updateVisControlVisibility() {
  if (!visChartType) return;
  const ctype = visChartType.value;

  // Defaults
  if (groupVisXCol) groupVisXCol.style.display = "block";
  if (groupVisYCol) groupVisYCol.style.display = "block";
  if (groupVisAggregation) groupVisAggregation.style.display = "block";
  if (visHeatmapNotice) visHeatmapNotice.style.display = "none";

  if (ctype === "bar") {
    if (lblVisXCol) lblVisXCol.innerHTML = 'X-Axis / Category: <span class="required-star">*</span>';
    if (lblVisYCol) lblVisYCol.textContent = "Y-Axis / Metric (Optional):";
    if (lblVisAggregation) lblVisAggregation.textContent = "Aggregation:";
  } else if (ctype === "line") {
    if (lblVisXCol) lblVisXCol.innerHTML = 'X-Axis / Sequence: <span class="required-star">*</span>';
    if (lblVisYCol) lblVisYCol.innerHTML = 'Y-Axis / Numerical Metric: <span class="required-star">*</span>';
    if (lblVisAggregation) lblVisAggregation.textContent = "Aggregation (if duplicate X):";
  } else if (ctype === "pie" || ctype === "donut") {
    if (lblVisXCol) lblVisXCol.innerHTML = 'Category Column: <span class="required-star">*</span>';
    if (lblVisYCol) lblVisYCol.textContent = "Value Column (Optional):";
    if (lblVisAggregation) lblVisAggregation.textContent = "Aggregation:";
  } else if (ctype === "histogram") {
    if (lblVisXCol) lblVisXCol.innerHTML = 'Numerical Column: <span class="required-star">*</span>';
    if (groupVisYCol) groupVisYCol.style.display = "none";
    if (groupVisAggregation) groupVisAggregation.style.display = "none";
  } else if (ctype === "scatter") {
    if (lblVisXCol) lblVisXCol.innerHTML = 'X-Axis (Numerical): <span class="required-star">*</span>';
    if (lblVisYCol) lblVisYCol.innerHTML = 'Y-Axis (Numerical): <span class="required-star">*</span>';
    if (groupVisAggregation) groupVisAggregation.style.display = "none";
  } else if (ctype === "box") {
    if (lblVisXCol) lblVisXCol.innerHTML = "Grouping Column (Optional):";
    if (lblVisYCol) lblVisYCol.innerHTML = 'Target Numerical Column: <span class="required-star">*</span>';
    if (groupVisAggregation) groupVisAggregation.style.display = "none";
  } else if (ctype === "heatmap") {
    if (groupVisXCol) groupVisXCol.style.display = "none";
    if (groupVisYCol) groupVisYCol.style.display = "none";
    if (groupVisAggregation) groupVisAggregation.style.display = "none";
    if (visHeatmapNotice) visHeatmapNotice.style.display = "block";
  }
}

function updateDashboardUI() {
  const count = dashboardCharts.length;
  if (dashboardCountBadge) {
    dashboardCountBadge.textContent = `${count} ${count === 1 ? "Chart" : "Charts"}`;
  }
  if (visEmptyState) {
    visEmptyState.style.display = count === 0 ? "block" : "none";
  }
  if (btnDownloadAllCharts) {
    btnDownloadAllCharts.style.display = count > 0 ? "inline-flex" : "none";
  }
  if (btnRegenerateAllCharts) {
    btnRegenerateAllCharts.style.display = count > 0 ? "inline-flex" : "none";
  }
  if (btnClearDashboard) {
    btnClearDashboard.style.display = count > 0 ? "inline-flex" : "none";
  }
}

function clearDashboardCharts() {
  dashboardCharts.forEach((item) => {
    if (item.instance && typeof item.instance.destroy === "function") {
      item.instance.destroy();
    }
  });
  dashboardCharts = [];
  if (chartsDashboardGrid) {
    chartsDashboardGrid.innerHTML = "";
  }
  updateDashboardUI();
}

function removeDashboardChart(chartCardId) {
  const idx = dashboardCharts.findIndex((c) => c.id === chartCardId);
  if (idx !== -1) {
    const item = dashboardCharts[idx];
    if (item.instance && typeof item.instance.destroy === "function") {
      item.instance.destroy();
    }
    dashboardCharts.splice(idx, 1);
  }
  const el = document.getElementById(chartCardId);
  if (el) el.remove();
  updateDashboardUI();
}

function exportChartPng(chartCardId, chartTitle) {
  const cardEl = document.getElementById(chartCardId);
  if (!cardEl) return;
  const canvas = cardEl.querySelector("canvas");
  if (!canvas) return;

  try {
    // Render on an off-screen canvas with solid white background for high quality export
    const exportCanvas = document.createElement("canvas");
    exportCanvas.width = canvas.width || 800;
    exportCanvas.height = canvas.height || 600;
    const expCtx = exportCanvas.getContext("2d");
    expCtx.fillStyle = "#ffffff";
    expCtx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
    expCtx.drawImage(canvas, 0, 0);

    const url = exportCanvas.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url;
    const safeTitle = (chartTitle || "data_chart").toLowerCase().replace(/[^a-z0-9]+/g, "_");
    a.download = `data_detective_${safeTitle}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch (err) {
    showVisError("Could not export chart as PNG: " + (err.message || err));
  }
}

async function downloadAllDashboardCharts() {
  if (dashboardCharts.length === 0) return;
  for (let i = 0; i < dashboardCharts.length; i++) {
    const item = dashboardCharts[i];
    exportChartPng(item.id, item.payload.title);
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}

async function regenerateAllChartsOnActiveDataset() {
  if (dashboardCharts.length === 0) return;
  const baseUrl = checkBackendConfigured();
  if (!baseUrl) return;

  const itemsToRebuild = [...dashboardCharts];
  clearDashboardCharts();

  for (const item of itemsToRebuild) {
    const cfg = item.requestConfig;
    const file = getActiveDatasetFile();
    if (!file) continue;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("chart_type", cfg.chartType);
    if (cfg.xCol) formData.append("x_column", cfg.xCol);
    if (cfg.yCol) formData.append("y_column", cfg.yCol);
    if (cfg.agg) formData.append("aggregation", cfg.agg);
    if (cfg.title) formData.append("title", cfg.title);

    try {
      const resp = await fetch(`${baseUrl}/api/visualize`, { method: "POST", body: formData });
      if (resp.ok) {
        const payload = await resp.json();
        addChartToDashboard(payload, activeVisSource, cfg);
      }
    } catch (e) {
      console.warn("Could not regenerate chart:", e);
    }
  }
}

async function generateVisualizationChart() {
  dismissVisError();

  const baseUrl = checkBackendConfigured();
  if (!baseUrl) return;

  const file = getActiveDatasetFile();
  if (!file) {
    showVisError("No dataset available. Please upload a CSV, Excel, or JSON dataset first.");
    return;
  }

  const ctype = visChartType ? visChartType.value : "bar";
  const xCol = visXCol ? visXCol.value : "";
  const yCol = visYCol ? visYCol.value : "";
  const agg = visAggregation ? visAggregation.value : "count";
  const title = visChartTitle ? visChartTitle.value.trim() : "";
  const meta = getActiveDatasetMeta();
  const allCols = meta.columns || [];

  // Dynamic Client-side Validations per Chart Type
  if (ctype === "bar") {
    if (!xCol) {
      showVisError("Bar Chart requires an X-Axis category column. Please select a column.");
      return;
    }
    if (yCol && !isColumnNumericByName(yCol) && agg !== "count") {
      showVisError(
        `Aggregation '${agg.toUpperCase()}' cannot be computed on categorical column '${yCol}'. Please choose 'Count' or select a numerical Y-axis column.`
      );
      return;
    }
  } else if (ctype === "line") {
    if (!xCol) {
      showVisError("Line Chart requires an X-Axis (date, sequence, or category) column.");
      return;
    }
    if (!yCol) {
      showVisError("Line Chart requires a numerical Y-Axis metric column.");
      return;
    }
    if (!isColumnNumericByName(yCol)) {
      showVisError(`Line Chart requires a numerical Y-Axis metric column. Column '${yCol}' is categorical.`);
      return;
    }
  } else if (ctype === "pie" || ctype === "donut") {
    const chartName = ctype === "donut" ? "Donut" : "Pie";
    if (!xCol) {
      showVisError(`${chartName} Chart requires a category column selected for X-Axis.`);
      return;
    }
    if (yCol && !isColumnNumericByName(yCol) && agg !== "count") {
      showVisError(
        `Aggregation '${agg.toUpperCase()}' cannot be computed on categorical column '${yCol}'. Please choose 'Count' or select a numerical value column.`
      );
      return;
    }
  } else if (ctype === "histogram") {
    if (!xCol) {
      showVisError("Histogram requires a numerical column selected for X-Axis.");
      return;
    }
    if (!isColumnNumericByName(xCol)) {
      showVisError(`Histogram requires a numerical column. Column '${xCol}' is categorical.`);
      return;
    }
  } else if (ctype === "scatter") {
    if (!xCol || !yCol) {
      showVisError("Scatter Plot requires both X-Axis and Y-Axis numerical columns.");
      return;
    }
    if (xCol === yCol) {
      showVisError("Scatter Plot requires two distinct numerical columns for X and Y axes.");
      return;
    }
    if (!isColumnNumericByName(xCol)) {
      showVisError(`Scatter Plot X-Axis must be numerical. Column '${xCol}' is categorical.`);
      return;
    }
    if (!isColumnNumericByName(yCol)) {
      showVisError(`Scatter Plot Y-Axis must be numerical. Column '${yCol}' is categorical.`);
      return;
    }
  } else if (ctype === "box") {
    const targetCol = yCol || xCol;
    if (!targetCol) {
      showVisError("Box Plot requires a target numerical column (select for Target Column).");
      return;
    }
    if (!isColumnNumericByName(targetCol)) {
      showVisError(`Box Plot target feature must be numerical. Column '${targetCol}' is categorical.`);
      return;
    }
  } else if (ctype === "heatmap") {
    const numCols = allCols.filter((c) => isColumnNumericByName(c));
    if (numCols.length < 2) {
      showVisError("Correlation Heatmap requires at least 2 numerical features in the dataset.");
      return;
    }
  }

  // Set loading state
  if (btnGenerateChart) {
    btnGenerateChart.disabled = true;
    btnGenerateChart.classList.add("loading");
  }
  if (visLoadingIndicator) {
    visLoadingIndicator.style.display = "inline-flex";
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("chart_type", ctype);
  if (xCol) formData.append("x_column", xCol);
  if (yCol) formData.append("y_column", yCol);
  if (agg) formData.append("aggregation", agg);
  if (title) formData.append("title", title);

  try {
    const response = await fetch(`${baseUrl}/api/visualize`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Visualization failed (${response.status})`);
    }

    addChartToDashboard(data, activeVisSource, {
      chartType: ctype,
      xCol,
      yCol,
      agg,
      title,
    });
    dismissVisError();
  } catch (error) {
    showVisError(error.message || "Failed to generate visualization chart.");
  } finally {
    if (btnGenerateChart) {
      btnGenerateChart.disabled = false;
      btnGenerateChart.classList.remove("loading");
    }
    if (visLoadingIndicator) {
      visLoadingIndicator.style.display = "none";
    }
  }
}

function addChartToDashboard(payload, source, requestConfig) {
  if (!chartsDashboardGrid) return;

  const chartCardId = "chart_card_" + Date.now() + "_" + Math.floor(Math.random() * 1000);
  const card = document.createElement("div");
  card.className = "chart-card";
  card.id = chartCardId;

  const isCleaned = source === "cleaned";
  const sourceLabel = isCleaned ? "Cleaned Dataset" : "Original Dataset";
  const sourceBadgeClass = isCleaned ? "badge-source-clean" : "badge-source-orig";

  // Build Statistics Snippet
  let statStripHtml = "";
  const stats = payload.statistics || {};
  const statItems = [];
  if (stats.pearson_correlation !== undefined && stats.pearson_correlation !== null) {
    statItems.push(`<span class="chart-stat-item">Correlation (r): <strong>${stats.pearson_correlation}</strong></span>`);
  }
  if (stats.points_rendered !== undefined) {
    statItems.push(`<span class="chart-stat-item">Points: <strong>${stats.points_rendered}</strong></span>`);
  }
  if (stats.category_count !== undefined) {
    statItems.push(`<span class="chart-stat-item">Categories: <strong>${stats.category_count}</strong></span>`);
  }
  if (stats.groups_evaluated !== undefined) {
    statItems.push(`<span class="chart-stat-item">Groups: <strong>${stats.groups_evaluated}</strong></span>`);
  }
  if (stats.total_finite_points !== undefined) {
    statItems.push(`<span class="chart-stat-item">Finite Observations: <strong>${stats.total_finite_points}</strong></span>`);
  }
  if (statItems.length > 0) {
    statStripHtml = `<div class="chart-stat-strip">${statItems.join("")}</div>`;
  }

  card.innerHTML = `
    <div class="chart-card-header">
      <div class="chart-card-title-group">
        <h4 class="chart-card-title">${escapeHtml(payload.title || "Visualization")}</h4>
        <div class="chart-badges-wrap">
          <span class="badge-chart-type">${escapeHtml(payload.chart_type)}</span>
          <span class="badge-dataset-source ${sourceBadgeClass}">${sourceLabel}</span>
        </div>
      </div>
      <div class="chart-card-actions">
        <button class="btn-chart-action btn-export-png" title="Download PNG" type="button">
          &#128247; PNG
        </button>
        <button class="btn-chart-action btn-chart-remove" title="Remove Chart" type="button">
          &times;
        </button>
      </div>
    </div>
    ${statStripHtml}
    <div class="chart-canvas-container">
      <canvas></canvas>
    </div>
  `;

  chartsDashboardGrid.appendChild(card);

  const canvas = card.querySelector("canvas");
  const ctype = payload.chart_type;
  let chartInstance = null;

  if (ctype === "box") {
    renderCustomBoxPlot(canvas, payload.box_data, payload.axis_info);
  } else if (ctype === "heatmap") {
    renderCustomHeatmap(canvas, payload.columns, payload.matrix);
  } else {
    chartInstance = renderChartJsInstance(canvas, payload);
  }

  // Hook actions
  const btnExport = card.querySelector(".btn-export-png");
  if (btnExport) {
    btnExport.addEventListener("click", () => {
      exportChartPng(chartCardId, payload.title);
    });
  }

  const btnRemove = card.querySelector(".btn-chart-remove");
  if (btnRemove) {
    btnRemove.addEventListener("click", () => {
      removeDashboardChart(chartCardId);
    });
  }

  dashboardCharts.push({
    id: chartCardId,
    chartType: ctype,
    payload: payload,
    source: source,
    requestConfig: requestConfig,
    instance: chartInstance,
    canvas: canvas,
  });

  updateDashboardUI();
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderChartJsInstance(canvas, payload) {
  const ctype = payload.chart_type;
  let chartJsType = ctype;
  if (ctype === "histogram") chartJsType = "bar";
  if (ctype === "donut") chartJsType = "doughnut";

  const ctx = canvas.getContext("2d");

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 350 },
    plugins: {
      legend: {
        display: ["pie", "donut", "doughnut"].includes(chartJsType),
        position: "bottom",
        labels: { boxWidth: 12, font: { size: 11 } },
      },
      tooltip: {
        backgroundColor: "#0f172a",
        titleColor: "#ffffff",
        bodyColor: "#ffffff",
        cornerRadius: 6,
        padding: 8,
      },
    },
  };

  if (["bar", "histogram", "line", "scatter"].includes(chartJsType)) {
    options.scales = {
      x: {
        grid: { color: "#f1f5f9" },
        ticks: { font: { size: 10 }, maxRotation: 45 },
        title: {
          display: Boolean(payload.axis_info && payload.axis_info.x_label),
          text: payload.axis_info ? payload.axis_info.x_label : "",
          font: { size: 11, weight: "bold" },
        },
      },
      y: {
        grid: { color: "#f1f5f9" },
        ticks: { font: { size: 10 } },
        title: {
          display: Boolean(payload.axis_info && payload.axis_info.y_label),
          text: payload.axis_info ? payload.axis_info.y_label : "",
          font: { size: 11, weight: "bold" },
        },
      },
    };
  }

  if (chartJsType === "scatter") {
    options.scales.x.type = "linear";
    options.scales.x.position = "bottom";
  }

  return new Chart(ctx, {
    type: chartJsType,
    data: {
      labels: payload.labels || [],
      datasets: payload.datasets || [],
    },
    options: options,
  });
}

function renderCustomBoxPlot(canvas, boxData, axisInfo) {
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width > 0 ? rect.width : (canvas.parentElement ? canvas.parentElement.clientWidth || 440 : 440);
  const h = rect.height > 0 ? rect.height : (canvas.parentElement ? canvas.parentElement.clientHeight || 300 : 300);

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  if (!boxData || boxData.length === 0) {
    ctx.fillStyle = "#64748b";
    ctx.font = "14px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("No numerical data available for box plot", w / 2, h / 2);
    return;
  }

  let allMin = Infinity;
  let allMax = -Infinity;
  boxData.forEach((g) => {
    if (g.lower_whisker !== null && g.lower_whisker < allMin) allMin = g.lower_whisker;
    if (g.min !== null && g.min < allMin) allMin = g.min;
    if (g.upper_whisker !== null && g.upper_whisker > allMax) allMax = g.upper_whisker;
    if (g.max !== null && g.max > allMax) allMax = g.max;
    (g.outliers || []).forEach((out) => {
      if (out < allMin) allMin = out;
      if (out > allMax) allMax = out;
    });
  });

  if (!isFinite(allMin) || !isFinite(allMax)) {
    allMin = 0;
    allMax = 100;
  }
  if (allMin === allMax) {
    allMin -= 1;
    allMax += 1;
  }

  const padding = (allMax - allMin) * 0.1 || 1;
  const yMin = allMin - padding;
  const yMax = allMax + padding;

  const marginLeft = 65;
  const marginRight = 25;
  const marginTop = 25;
  const marginBottom = 45;
  const plotW = Math.max(10, w - marginLeft - marginRight);
  const plotH = Math.max(10, h - marginTop - marginBottom);

  const scaleY = (val) => {
    return marginTop + plotH - ((val - yMin) / (yMax - yMin)) * plotH;
  };

  // Draw 5 horizontal grid lines & Y labels
  ctx.strokeStyle = "#e2e8f0";
  ctx.fillStyle = "#64748b";
  ctx.font = "11px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
  ctx.textAlign = "right";
  ctx.lineWidth = 1;

  for (let i = 0; i <= 4; i++) {
    const val = yMin + (i / 4) * (yMax - yMin);
    const yPos = scaleY(val);
    ctx.beginPath();
    ctx.moveTo(marginLeft, yPos);
    ctx.lineTo(marginLeft + plotW, yPos);
    ctx.stroke();

    ctx.fillText(Number(val.toFixed(2)).toLocaleString(), marginLeft - 8, yPos + 4);
  }

  // Draw each box group
  const n = boxData.length;
  const groupW = plotW / n;
  const boxW = Math.min(50, Math.max(18, groupW * 0.55));

  boxData.forEach((g, idx) => {
    const cx = marginLeft + (idx + 0.5) * groupW;

    if (g.median === null || g.q1 === null || g.q3 === null) {
      ctx.fillStyle = "#94a3b8";
      ctx.textAlign = "center";
      ctx.fillText("N/A", cx, marginTop + plotH / 2);
    } else {
      const yLowWhisker = scaleY(g.lower_whisker !== null ? g.lower_whisker : g.min);
      const yUpWhisker = scaleY(g.upper_whisker !== null ? g.upper_whisker : g.max);
      const yQ1 = scaleY(g.q1);
      const yQ3 = scaleY(g.q3);
      const yMedian = scaleY(g.median);

      // Whisker vertical lines
      ctx.strokeStyle = "#1d4ed8";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cx, yUpWhisker);
      ctx.lineTo(cx, yQ3);
      ctx.moveTo(cx, yQ1);
      ctx.lineTo(cx, yLowWhisker);
      ctx.stroke();

      // Whisker caps
      ctx.beginPath();
      ctx.moveTo(cx - boxW * 0.35, yUpWhisker);
      ctx.lineTo(cx + boxW * 0.35, yUpWhisker);
      ctx.moveTo(cx - boxW * 0.35, yLowWhisker);
      ctx.lineTo(cx + boxW * 0.35, yLowWhisker);
      ctx.stroke();

      // Box body (Q1 to Q3)
      ctx.fillStyle = "rgba(37, 99, 235, 0.18)";
      ctx.strokeStyle = "#2563eb";
      ctx.lineWidth = 1.75;
      const boxTop = Math.min(yQ1, yQ3);
      const boxH = Math.max(2, Math.abs(yQ1 - yQ3));
      ctx.fillRect(cx - boxW / 2, boxTop, boxW, boxH);
      ctx.strokeRect(cx - boxW / 2, boxTop, boxW, boxH);

      // Median line
      ctx.strokeStyle = "#1e3a8a";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(cx - boxW / 2, yMedian);
      ctx.lineTo(cx + boxW / 2, yMedian);
      ctx.stroke();

      // Outlier dots
      if (g.outliers && g.outliers.length > 0) {
        ctx.fillStyle = "#ef4444";
        g.outliers.forEach((out) => {
          const yOut = scaleY(out);
          ctx.beginPath();
          ctx.arc(cx, yOut, 3.5, 0, Math.PI * 2);
          ctx.fill();
        });
      }
    }

    // X Group Label
    ctx.fillStyle = "#0f172a";
    ctx.font = "11px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
    ctx.textAlign = "center";
    let groupLabel = String(g.group || "");
    if (groupLabel.length > 12) groupLabel = groupLabel.slice(0, 10) + "...";
    ctx.fillText(groupLabel, cx, marginTop + plotH + 18);
  });
}

function renderCustomHeatmap(canvas, columns, matrix) {
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const w = rect.width > 0 ? rect.width : (canvas.parentElement ? canvas.parentElement.clientWidth || 440 : 440);
  const h = rect.height > 0 ? rect.height : (canvas.parentElement ? canvas.parentElement.clientHeight || 300 : 300);

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, w, h);

  if (!columns || columns.length === 0 || !matrix || matrix.length === 0) {
    ctx.fillStyle = "#64748b";
    ctx.font = "14px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("No numerical features available for heatmap", w / 2, h / 2);
    return;
  }

  const n = columns.length;
  const marginLeft = 85;
  const marginBottom = 65;
  const marginTop = 20;
  const marginRight = 20;

  const availW = Math.max(10, w - marginLeft - marginRight);
  const availH = Math.max(10, h - marginTop - marginBottom);
  const cellSize = Math.min(availW / n, availH / n, 50);

  for (let r = 0; r < n; r++) {
    // Row Label
    ctx.fillStyle = "#0f172a";
    ctx.font = "11px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
    ctx.textAlign = "right";
    let rowName = columns[r];
    if (rowName.length > 11) rowName = rowName.slice(0, 9) + "..";
    ctx.fillText(rowName, marginLeft - 8, marginTop + (r + 0.6) * cellSize);

    for (let c = 0; c < n; c++) {
      const val = matrix[r][c];
      const xPos = marginLeft + c * cellSize;
      const yPos = marginTop + r * cellSize;

      let fillColor = "#ffffff";
      let textColor = "#0f172a";

      if (val !== null && val !== undefined) {
        if (val >= 0) {
          const ratio = Math.min(1, Math.max(0, val));
          const red = Math.round(255 - ratio * (255 - 37));
          const green = Math.round(255 - ratio * (255 - 99));
          const blue = Math.round(255 - ratio * (255 - 235));
          fillColor = `rgb(${red}, ${green}, ${blue})`;
          if (ratio > 0.55) textColor = "#ffffff";
        } else {
          const ratio = Math.min(1, Math.max(0, Math.abs(val)));
          const red = Math.round(255 - ratio * (255 - 239));
          const green = Math.round(255 - ratio * (255 - 68));
          const blue = Math.round(255 - ratio * (255 - 68));
          fillColor = `rgb(${red}, ${green}, ${blue})`;
          if (ratio > 0.55) textColor = "#ffffff";
        }
      }

      ctx.fillStyle = fillColor;
      ctx.fillRect(xPos, yPos, cellSize - 1, cellSize - 1);

      if (val !== null && val !== undefined && cellSize >= 24) {
        ctx.fillStyle = textColor;
        ctx.font = "10px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(val.toFixed(2), xPos + cellSize / 2, yPos + cellSize / 2 + 3);
      }
    }
  }

  // Draw Column Labels (angled at 45 degrees)
  ctx.fillStyle = "#0f172a";
  ctx.font = "11px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
  ctx.textAlign = "left";

  for (let c = 0; c < n; c++) {
    const xPos = marginLeft + (c + 0.5) * cellSize;
    const yPos = marginTop + n * cellSize + 10;
    ctx.save();
    ctx.translate(xPos, yPos);
    ctx.rotate(Math.PI / 4);
    let colName = columns[c];
    if (colName.length > 12) colName = colName.slice(0, 10) + "..";
    ctx.fillText(colName, 0, 0);
    ctx.restore();
  }
}

/* -------------------------------------------------------------
 * 9. Event Listeners for Visualization Studio
 * ------------------------------------------------------------- */
function openVisStudioSection() {
  if (visualizationStudioSection) {
    visualizationStudioSection.style.display = "block";
    updateVisDatasetSwitcherUI();
    updateReportDatasetSwitcherUI();
    updateReportDatasetSwitcherUI();
    populateVisualizationDropdowns();
    visualizationStudioSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

if (btnOpenVisualizationStudio) {
  btnOpenVisualizationStudio.addEventListener("click", openVisStudioSection);
}

if (btnGoToVisFromEda) {
  btnGoToVisFromEda.addEventListener("click", openVisStudioSection);
}

if (btnGoToVisFromCleaner) {
  btnGoToVisFromCleaner.addEventListener("click", openVisStudioSection);
}

if (btnVisScrollToCleaning) {
  btnVisScrollToCleaning.addEventListener("click", () => {
    if (cleaningStudioSection) {
      cleaningStudioSection.style.display = "block";
      cleaningStudioSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}

if (btnVisScrollToTop) {
  btnVisScrollToTop.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

if (btnSourceOriginal) {
  btnSourceOriginal.addEventListener("click", () => {
    activeVisSource = "original";
    updateVisDatasetSwitcherUI();
    updateReportDatasetSwitcherUI();
    updateReportDatasetSwitcherUI();
    populateVisualizationDropdowns();
  });
}

if (btnSourceCleaned) {
  btnSourceCleaned.addEventListener("click", () => {
    if (cleanedDatasetFile) {
      activeVisSource = "cleaned";
      updateVisDatasetSwitcherUI();
    updateReportDatasetSwitcherUI();
      populateVisualizationDropdowns();
    }
  });
}

if (visChartType) {
  visChartType.addEventListener("change", () => {
    dismissVisError();
    updateVisControlVisibility();
    updateVisAggregationOptions();
  });
}

if (visXCol) {
  visXCol.addEventListener("change", () => {
    dismissVisError();
    updateVisAggregationOptions();
  });
}

if (visYCol) {
  visYCol.addEventListener("change", () => {
    dismissVisError();
    updateVisAggregationOptions();
  });
}

if (visAggregation) {
  visAggregation.addEventListener("change", () => {
    dismissVisError();
  });
}

if (visChartTitle) {
  visChartTitle.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      generateVisualizationChart();
    }
  });
}

if (btnGenerateChart) {
  btnGenerateChart.addEventListener("click", (e) => {
    if (e && typeof e.preventDefault === "function") {
      e.preventDefault();
    }
    generateVisualizationChart();
  });
}

if (btnResetVisControls) {
  btnResetVisControls.addEventListener("click", () => {
    if (visChartType) visChartType.value = "bar";
    if (visXCol) visXCol.value = "";
    if (visYCol) visYCol.value = "";
    if (visAggregation) visAggregation.value = "count";
    if (visChartTitle) visChartTitle.value = "";
    dismissVisError();
    updateVisControlVisibility();
    updateVisAggregationOptions();
  });
}

if (btnDownloadAllCharts) {
  btnDownloadAllCharts.addEventListener("click", () => {
    downloadAllDashboardCharts();
  });
}

if (btnRegenerateAllCharts) {
  btnRegenerateAllCharts.addEventListener("click", () => {
    regenerateAllChartsOnActiveDataset();
  });
}

if (btnClearDashboard) {
  btnClearDashboard.addEventListener("click", () => {
    if (confirm("Are you sure you want to clear all charts from the dashboard?")) {
      clearDashboardCharts();
    }
  });
}

// Window resize listener to redraw custom box plots and heatmaps
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    dashboardCharts.forEach((item) => {
      if (item.chartType === "box" && item.canvas) {
        renderCustomBoxPlot(item.canvas, item.payload.box_data, item.payload.axis_info);
      } else if (item.chartType === "heatmap" && item.canvas) {
        renderCustomHeatmap(item.canvas, item.payload.columns, item.payload.matrix);
      }
    });
  }, 150);
});

/* -------------------------------------------------------------
 * 10. Phase 6: Automated EDA Report Generation Studio
 * ------------------------------------------------------------- */
function openReportStudioSection() {
  if (reportStudioSection) {
    reportStudioSection.style.display = "block";
    updateReportDatasetSwitcherUI();
    reportStudioSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function updateReportDatasetSwitcherUI() {
  if (!labelReportSourceOriginal || !labelReportSourceCleaned) return;

  if (originalDatasetMeta) {
    labelReportSourceOriginal.textContent = `Original (${originalDatasetMeta.filename}) • ${originalDatasetMeta.row_count} rows`;
  } else {
    labelReportSourceOriginal.textContent = "Original Dataset";
  }

  if (cleanedDatasetFile && cleanedDatasetMeta) {
    btnReportSourceCleaned.disabled = false;
    btnReportSourceCleaned.classList.remove("disabled");
    btnReportSourceCleaned.title = "Switch to Cleaned Dataset Report";
    labelReportSourceCleaned.textContent = `Cleaned (${cleanedDatasetMeta.filename}) • ${cleanedDatasetMeta.row_count} rows`;
  } else {
    btnReportSourceCleaned.disabled = true;
    btnReportSourceCleaned.classList.add("disabled");
    btnReportSourceCleaned.title = "Apply or download a cleaned dataset in Cleaning Studio first";
    labelReportSourceCleaned.textContent = "Cleaned Dataset (None)";
    if (activeReportSource === "cleaned") {
      activeReportSource = "original";
    }
  }

  if (activeReportSource === "original") {
    btnReportSourceOriginal.classList.add("active");
    btnReportSourceCleaned.classList.remove("active");
    if (activeReportSourceDetails) {
      const meta = originalDatasetMeta || {};
      activeReportSourceDetails.textContent = `${meta.filename || "Original"} (${meta.row_count || 0} rows, ${meta.column_count || 0} cols)`;
    }
  } else {
    btnReportSourceCleaned.classList.add("active");
    btnReportSourceOriginal.classList.remove("active");
    if (activeReportSourceDetails) {
      const meta = cleanedDatasetMeta || {};
      activeReportSourceDetails.textContent = `${meta.filename || "Cleaned"} (${meta.row_count || 0} rows, ${meta.column_count || 0} cols)`;
    }
  }
}

function showReportError(msg) {
  if (reportErrorMessage && reportErrorAlert) {
    reportErrorMessage.textContent = msg;
    reportErrorAlert.style.display = "flex";
    reportErrorAlert.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}

function dismissReportError() {
  if (reportErrorAlert) {
    reportErrorAlert.style.display = "none";
  }
}

function showReportSuccess(msg) {
  if (reportSuccessMessage && reportSuccessAlert) {
    reportSuccessMessage.textContent = msg;
    reportSuccessAlert.style.display = "flex";
  }
}

function dismissReportSuccess() {
  if (reportSuccessAlert) {
    reportSuccessAlert.style.display = "none";
  }
}

async function generateEdaReportPdf() {
  dismissReportError();
  dismissReportSuccess();

  const baseUrl = checkBackendConfigured();
  if (!baseUrl) return;

  let fileToReport = null;
  if (activeReportSource === "cleaned") {
    if (!cleanedDatasetFile) {
      showReportError("Cleaned dataset not found. Please clean a dataset first in the Cleaning Studio.");
      return;
    }
    fileToReport = cleanedDatasetFile;
  } else {
    fileToReport = originalDatasetFile || currentUploadedFile || stagedFile;
    if (!fileToReport) {
      showReportError("No dataset available. Please upload a dataset first.");
      return;
    }
  }

  if (btnGenerateReport) {
    btnGenerateReport.disabled = true;
  }
  if (reportLoadingIndicator) {
    reportLoadingIndicator.style.display = "inline-flex";
  }

  const formData = new FormData();
  formData.append("file", fileToReport);
  formData.append("dataset_type", activeReportSource);

  if (activeReportSource === "cleaned") {
    if (queuedCleaningOperations && queuedCleaningOperations.length > 0) {
      formData.append("operations", JSON.stringify(queuedCleaningOperations));
    }
    if (originalDatasetFile) {
      formData.append("original_file", originalDatasetFile);
    }
  }

  try {
    const response = await fetch(`${baseUrl}/api/report/generate`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Report compilation failed (${response.status})`);
    }

    const blob = await response.blob();

    // Construct download filename
    let downloadFileName = `data_detective_eda_report_${fileToReport.name.replace(/\.[^/.]+$/, "")}.pdf`;
    const disposition = response.headers.get("Content-Disposition");
    if (disposition && disposition.includes("filename=")) {
      const match = disposition.match(/filename="?([^";]+)"?/);
      if (match && match[1]) {
        downloadFileName = match[1];
      }
    }

    // Trigger instant browser download
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadFileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    lastGeneratedReportBlob = blob;
    lastGeneratedReportFileName = downloadFileName;
    if (btnDownloadReportAgain) {
      btnDownloadReportAgain.style.display = "inline-flex";
    }

    showReportSuccess(`Report '${downloadFileName}' compiled successfully! Your PDF download has started automatically.`);
  } catch (error) {
    showReportError(error.message || "Failed to generate EDA report.");
  } finally {
    if (btnGenerateReport) {
      btnGenerateReport.disabled = false;
    }
    if (reportLoadingIndicator) {
      reportLoadingIndicator.style.display = "none";
    }
  }
}

function downloadLastGeneratedReport() {
  if (!lastGeneratedReportBlob) return;
  const url = window.URL.createObjectURL(lastGeneratedReportBlob);
  const a = document.createElement("a");
  a.href = url;
  a.download = lastGeneratedReportFileName || "data_detective_eda_report.pdf";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// Event Listeners for Phase 6 Report Studio
if (btnOpenReportStudio) {
  btnOpenReportStudio.addEventListener("click", openReportStudioSection);
}
if (btnGoToReportFromEda) {
  btnGoToReportFromEda.addEventListener("click", openReportStudioSection);
}
if (btnGoToReportFromCleaner) {
  btnGoToReportFromCleaner.addEventListener("click", openReportStudioSection);
}
if (btnGoToReportFromVis) {
  btnGoToReportFromVis.addEventListener("click", openReportStudioSection);
}
if (btnReportScrollToVis) {
  btnReportScrollToVis.addEventListener("click", () => {
    if (visualizationStudioSection) {
      visualizationStudioSection.style.display = "block";
      visualizationStudioSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}
if (btnReportScrollToCleaning) {
  btnReportScrollToCleaning.addEventListener("click", () => {
    if (cleaningStudioSection) {
      cleaningStudioSection.style.display = "block";
      cleaningStudioSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}
if (btnReportScrollToTop) {
  btnReportScrollToTop.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}
if (btnReportSourceOriginal) {
  btnReportSourceOriginal.addEventListener("click", () => {
    activeReportSource = "original";
    updateReportDatasetSwitcherUI();
    dismissReportError();
    dismissReportSuccess();
  });
}
if (btnReportSourceCleaned) {
  btnReportSourceCleaned.addEventListener("click", () => {
    if (cleanedDatasetFile) {
      activeReportSource = "cleaned";
      updateReportDatasetSwitcherUI();
      dismissReportError();
      dismissReportSuccess();
    }
  });
}
if (btnDismissReportError) {
  btnDismissReportError.addEventListener("click", dismissReportError);
}
if (btnDismissReportSuccess) {
  btnDismissReportSuccess.addEventListener("click", dismissReportSuccess);
}
if (btnGenerateReport) {
  btnGenerateReport.addEventListener("click", (e) => {
    if (e && typeof e.preventDefault === "function") e.preventDefault();
    generateEdaReportPdf();
  });
}
if (btnDownloadReportAgain) {
  btnDownloadReportAgain.addEventListener("click", downloadLastGeneratedReport);
}

if (btnSaveBackendUrl) {
  btnSaveBackendUrl.addEventListener("click", () => {
    if (!inputBackendUrl) return;
    const rawVal = inputBackendUrl.value.trim().replace(/\/+$/, "");
    if (!rawVal) {
      showError("Please enter a valid FastAPI backend URL (e.g. https://your-backend.onrender.com).");
      return;
    }
    if (!rawVal.startsWith("http://") && !rawVal.startsWith("https://")) {
      showError("Backend URL must begin with http:// or https://");
      return;
    }
    try {
      localStorage.setItem("DATA_DETECTIVE_API_URL", rawVal);
      localStorage.setItem("API_BASE_URL", rawVal);
    } catch (e) {
      console.warn("Could not save backend URL to localStorage:", e);
    }
    if (typeof window !== "undefined") {
      window.DATA_DETECTIVE_CONFIG = window.DATA_DETECTIVE_CONFIG || {};
      window.DATA_DETECTIVE_CONFIG.API_BASE_URL = rawVal;
    }
    checkBackendHealth();
  });
}

if (btnResetBackendUrl) {
  btnResetBackendUrl.addEventListener("click", () => {
    try {
      localStorage.removeItem("DATA_DETECTIVE_API_URL");
      localStorage.removeItem("API_BASE_URL");
    } catch (e) {
      console.warn("Could not clear backend URL from localStorage:", e);
    }
    if (typeof window !== "undefined" && window.DATA_DETECTIVE_CONFIG) {
      window.DATA_DETECTIVE_CONFIG.API_BASE_URL = "";
    }
    if (inputBackendUrl) {
      inputBackendUrl.value = "";
    }
    checkBackendHealth();
  });
}

// Initial health check on page load
document.addEventListener("DOMContentLoaded", () => {
  checkBackendHealth();
  updatePipelineQueueUI();
  updateVisDatasetSwitcherUI();
  updateVisControlVisibility();
  updateReportDatasetSwitcherUI();
});

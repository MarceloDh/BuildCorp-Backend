const origenApi = new URL("http://127.0.0.1:8000");
window.BUILDCORP_API = new URL("/api/v4/", origenApi).href;

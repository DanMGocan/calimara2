import { api } from "./client.js";

export function fetchDataExport() {
  return api.get("/api/portabilitate/export");
}

export function importDataExport(data) {
  return api.post("/api/portabilitate/import", data);
}

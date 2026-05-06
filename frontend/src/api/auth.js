import { api } from "./client.js";

export const AUTH_GOOGLE_PATH = "/autentificare/google";

export const AUTH_GOOGLE_CALLBACK_PATH = "/auth/google/callback";

export const AUTH_SETUP_PATH = "/autentificare/configurare";

export function completeAuthSetup(data) {
  return api.post("/api/autentificare/finalizeaza-configurarea", data);
}

export function logout() {
  return api.get("/api/deconectare");
}

import { api } from "./client.js";

export const AUTH_LOGIN_PATH = "/autentificare";

export const AUTH_GOOGLE_PATH = "/autentificare/google";

export const AUTH_FACEBOOK_PATH = "/autentificare/facebook";

export const AUTH_GOOGLE_CALLBACK_PATH = "/auth/google/callback";

export const AUTH_SETUP_PATH = "/autentificare/configurare";

export function registerWithPassword(data) {
  return api.post("/api/autentificare/parola/inregistrare", data);
}

export function activatePasswordSignup(data) {
  return api.post("/api/autentificare/parola/activeaza", data);
}

export function resendActivationCode(data) {
  return api.post("/api/autentificare/parola/retrimite-cod", data);
}

export function loginWithPassword(data) {
  return api.post("/api/autentificare/parola/login", data);
}

export function requestPasswordReset(data) {
  return api.post("/api/autentificare/parola/resetare", data);
}

export function confirmPasswordReset(data) {
  return api.post("/api/autentificare/parola/resetare/confirma", data);
}

export function completeAuthSetup(data) {
  return api.post("/api/autentificare/finalizeaza-configurarea", data);
}

export function logout() {
  return api.get("/api/deconectare");
}

import { api } from "./client.js";
export { fetchMyReferrals } from "./referrals.js";

export function fetchPremiumPlans() {
  return api.get("/api/premium/planuri");
}

export function startPremiumCheckout(tier = "trubadur") {
  return api.post("/api/premium/plata", { tier });
}

export function fetchCoffeeOffer() {
  return api.get("/api/premium/cafea");
}

export function startCoffeeCheckout(quantity = 1) {
  return api.post("/api/premium/cafea", { quantity });
}

export function openPremiumPortal() {
  return api.post("/api/premium/portal", {});
}

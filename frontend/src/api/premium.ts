import { api } from "./client";

interface RedirectUrlResponse {
  url: string;
}

export const startPremiumCheckout = async () => {
  const { url } = await api.post<RedirectUrlResponse>("/api/premium/checkout");
  window.location.assign(url);
};

export const openCustomerPortal = async () => {
  const { url } = await api.post<RedirectUrlResponse>("/api/premium/portal");
  window.location.assign(url);
};

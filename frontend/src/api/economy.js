import { api } from "./client.js";

export function fetchShopState() {
  return api.get("/api/magazin/eu");
}

export function fetchPublicInventory(username) {
  return api.get(`/api/utilizator/${encodeURIComponent(username)}/inventar`);
}

export function purchaseShopItem(itemId) {
  return api.post(`/api/magazin/obiecte/${encodeURIComponent(itemId)}/cumpara`, {});
}

export function equipInventoryItem(itemId) {
  return api.post("/api/inventar/echipeaza", { item_id: itemId });
}

export function unequipInventorySlot(slot) {
  return api.delete(`/api/inventar/echipate/${encodeURIComponent(slot)}`);
}

export function fetchAdminShopItems() {
  return api.get("/api/moderare/magazin/obiecte");
}

export function createAdminShopItem(data) {
  return api.post("/api/moderare/magazin/obiecte", data);
}

export function updateAdminShopItem(itemId, data) {
  return api.put(`/api/moderare/magazin/obiecte/${encodeURIComponent(itemId)}`, data);
}


import { useCallback, useEffect, useState } from "react";
import { equipInventoryItem, fetchPublicInventory, fetchShopState, purchaseShopItem, unequipInventorySlot } from "../api/economy.js";
import { formatGologani, slotLabel, usernameHandle } from "../app/format.js";
import { useAsync } from "../app/hooks.js";
import { AuthRequired, PageShell, StatusPanel } from "../app/layout.jsx";
import { mainPath } from "../app/paths.js";

function CosmeticPreview({ item }) {
  return (
    <div className="cosmetic-preview" aria-hidden="true">
      {item?.asset_url ? <img src={item.asset_url} alt="" /> : <span>{item?.name?.slice(0, 2) || "G"}</span>}
    </div>
  );
}
function useShopState(user) {
  const [state, setState] = useState({ data: null, error: "", loading: Boolean(user) });

  const load = useCallback(async () => {
    if (!user) {
      setState({ data: null, error: "", loading: false });
      return;
    }
    setState((current) => ({ ...current, error: "", loading: true }));
    try {
      const data = await fetchShopState();
      setState({ data, error: "", loading: false });
    } catch (requestError) {
      setState({ data: null, error: requestError.message || "Nu am putut încărca magazinul.", loading: false });
    }
  }, [user?.id]);

  useEffect(() => {
    load();
  }, [load]);

  return [state, setState];
}
function ShopView({ user }) {
  const [{ data, error, loading }, setState] = useShopState(user);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  if (!user) return <AuthRequired />;

  const purchase = async (item) => {
    setBusy(`purchase-${item.id}`);
    setStatus("");
    try {
      const next = await purchaseShopItem(item.id);
      setState({ data: next, error: "", loading: false });
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut cumpăra obiectul.");
    } finally {
      setBusy("");
    }
  };

  const equip = async (item) => {
    setBusy(`equip-${item.id}`);
    setStatus("");
    try {
      const next = await equipInventoryItem(item.id);
      setState({ data: next, error: "", loading: false });
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut echipa obiectul.");
    } finally {
      setBusy("");
    }
  };

  return (
    <PageShell kicker="magazin" title="Magazin" sub={`${formatGologani(data?.balance ?? user.gologani_balance)} disponibili.`}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca magazinul">{error}</StatusPanel> : null}
      {status ? <div className="inline-error">{status}</div> : null}
      {data?.items?.length ? (
        <div className="shop-grid">
          {data.items.map((item) => {
            const canAfford = (data.balance ?? 0) >= item.price;
            return (
              <article className="shop-card" key={item.id}>
                <CosmeticPreview item={item} />
                <div className="piece-card-kicker">{slotLabel(item.slot)}</div>
                <h2 className="piece-card-title">{item.name}</h2>
                <p className="piece-card-excerpt">{item.description || "Obiect cosmetic pentru profil."}</p>
                <div className="shop-card-foot">
                  <span className="shop-price">{formatGologani(item.price)}</span>
                  {item.equipped ? (
                    <button className="cal-btn" type="button" disabled>Echipat</button>
                  ) : item.owned ? (
                    <button className="cal-btn primary" type="button" disabled={busy === `equip-${item.id}`} onClick={() => equip(item)}>
                      {busy === `equip-${item.id}` ? "Se echipează..." : "Echipează"}
                    </button>
                  ) : (
                    <button className="cal-btn primary" type="button" disabled={!canAfford || busy === `purchase-${item.id}`} onClick={() => purchase(item)}>
                      {busy === `purchase-${item.id}` ? "Se cumpără..." : "Cumpără"}
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      ) : !loading && !error ? <StatusPanel title="Magazinul este gol" /> : null}
    </PageShell>
  );
}
function InventoryView({ user }) {
  const [{ data, error, loading }, setState] = useShopState(user);
  const [busy, setBusy] = useState("");
  const [status, setStatus] = useState("");

  if (!user) return <AuthRequired />;

  const equip = async (item) => {
    setBusy(`equip-${item.id}`);
    setStatus("");
    try {
      const next = await equipInventoryItem(item.id);
      setState({ data: next, error: "", loading: false });
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut echipa obiectul.");
    } finally {
      setBusy("");
    }
  };

  const unequip = async (slot) => {
    setBusy(`unequip-${slot}`);
    setStatus("");
    try {
      const next = await unequipInventorySlot(slot);
      setState({ data: next, error: "", loading: false });
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut dezechipa obiectul.");
    } finally {
      setBusy("");
    }
  };

  return (
    <PageShell kicker="inventar" title="Inventar" sub={`${formatGologani(data?.balance ?? user.gologani_balance)} disponibili.`}>
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca inventarul">{error}</StatusPanel> : null}
      {status ? <div className="inline-error">{status}</div> : null}
      {data?.equipped?.length ? (
        <section className="inventory-section" aria-label="Echipate">
          <div className="piece-card-kicker">echipate</div>
          <div className="inventory-list">
            {data.equipped.map((entry) => (
              <article className="inventory-row" key={entry.slot}>
                <CosmeticPreview item={entry.item} />
                <div>
                  <div className="inventory-title">{entry.item.name}</div>
                  <div className="inventory-meta">{slotLabel(entry.slot)}</div>
                </div>
                <button className="cal-btn" type="button" disabled={busy === `unequip-${entry.slot}`} onClick={() => unequip(entry.slot)}>
                  {busy === `unequip-${entry.slot}` ? "Se scoate..." : "Dezechipează"}
                </button>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      {data?.inventory?.length ? (
        <section className="inventory-section" aria-label="Inventar">
          <div className="piece-card-kicker">obiecte</div>
          <div className="shop-grid">
            {data.inventory.map((entry) => (
              <article className="shop-card" key={entry.id}>
                <CosmeticPreview item={entry.item} />
                <div className="piece-card-kicker">{slotLabel(entry.item.slot)}</div>
                <h2 className="piece-card-title">{entry.item.name}</h2>
                <p className="piece-card-excerpt">{entry.item.description || "Obiect cosmetic pentru profil."}</p>
                <div className="shop-card-foot">
                  <span className="shop-price">în inventar</span>
                  {entry.item.equipped ? (
                    <button className="cal-btn" type="button" disabled>Echipat</button>
                  ) : (
                    <button className="cal-btn primary" type="button" disabled={busy === `equip-${entry.item.id}`} onClick={() => equip(entry.item)}>
                      {busy === `equip-${entry.item.id}` ? "Se echipează..." : "Echipează"}
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : !loading && !error ? (
        <StatusPanel
          title="Inventarul este gol"
          action={<a className="cal-btn primary" href={mainPath("/magazin")}>Deschide magazinul</a>}
        />
      ) : null}
    </PageShell>
  );
}
function PublicInventoryView({ username }) {
  const { data, error, loading } = useAsync(() => fetchPublicInventory(username), [username]);
  const owner = data?.owner;

  return (
    <PageShell
      kicker="inventar"
      title={owner?.username ? `Inventarul lui ${usernameHandle(owner.username)}` : "Inventar"}
      sub={owner ? `${formatGologani(owner.gologani_balance)} în cont.` : ""}
    >
      {loading ? <StatusPanel title="Se încarcă" /> : null}
      {error ? <StatusPanel title="Nu am putut încărca inventarul">{error}</StatusPanel> : null}
      {data?.equipped?.length ? (
        <section className="inventory-section" aria-label="Echipate">
          <div className="piece-card-kicker">echipate</div>
          <div className="inventory-list">
            {data.equipped.map((entry) => (
              <article className="inventory-row" key={entry.slot}>
                <CosmeticPreview item={entry.item} />
                <div>
                  <div className="inventory-title">{entry.item.name}</div>
                  <div className="inventory-meta">{slotLabel(entry.slot)}</div>
                </div>
                <span className="shop-price">echipat</span>
              </article>
            ))}
          </div>
        </section>
      ) : null}
      {data?.inventory?.length ? (
        <section className="inventory-section" aria-label="Inventar">
          <div className="piece-card-kicker">obiecte</div>
          <div className="shop-grid">
            {data.inventory.map((entry) => (
              <article className="shop-card" key={entry.id}>
                <CosmeticPreview item={entry.item} />
                <div className="piece-card-kicker">{slotLabel(entry.item.slot)}</div>
                <h2 className="piece-card-title">{entry.item.name}</h2>
                <p className="piece-card-excerpt">{entry.item.description || "Obiect cosmetic pentru profil."}</p>
                <div className="shop-card-foot">
                  <span className="shop-price">{entry.item.equipped ? "echipat" : "în inventar"}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : !loading && !error ? (
        <StatusPanel title="Inventarul este gol" />
      ) : null}
    </PageShell>
  );
}

export default function EconomyRoute({ route, user }) {
  if (route.name === "publicInventory") return <PublicInventoryView username={route.username} />;
  if (route.name === "inventory") return <InventoryView user={user} />;
  return <ShopView user={user} />;
}

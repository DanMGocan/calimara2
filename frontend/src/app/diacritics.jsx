import { useCallback, useEffect, useRef, useState } from "react";
import { fetchDiacriticsQuota } from "../api/writing.js";
import { formatDateTime, formatNumber } from "./format.js";
import { mainPath } from "./paths.js";

const PROGRESS_COMPLETE_HIDE_MS = 520;

function estimateDiacriticsDuration(textLength) {
  return Math.min(24000, Math.max(4200, 2200 + textLength * 1.1));
}

export function useDiacriticsProgress() {
  const closeTimerRef = useRef(0);
  const [progressState, setProgressState] = useState({
    active: false,
    phase: "idle",
    progress: 0,
    startedAt: 0,
    textLength: 0
  });

  const clearCloseTimer = useCallback(() => {
    if (!closeTimerRef.current) return;
    window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = 0;
  }, []);

  const startDiacriticsProgress = useCallback(({ title = "", content = "" } = {}) => {
    clearCloseTimer();
    setProgressState({
      active: true,
      phase: "processing",
      progress: 3,
      startedAt: Date.now(),
      textLength: String(title || "").length + String(content || "").length
    });
  }, [clearCloseTimer]);

  const finishDiacriticsProgress = useCallback(() => {
    clearCloseTimer();
    setProgressState((current) => ({
      ...current,
      active: true,
      phase: "complete",
      progress: 100
    }));
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = 0;
      setProgressState({
        active: false,
        phase: "idle",
        progress: 0,
        startedAt: 0,
        textLength: 0
      });
    }, PROGRESS_COMPLETE_HIDE_MS);
  }, [clearCloseTimer]);

  const failDiacriticsProgress = useCallback(() => {
    clearCloseTimer();
    setProgressState({
      active: false,
      phase: "idle",
      progress: 0,
      startedAt: 0,
      textLength: 0
    });
  }, [clearCloseTimer]);

  useEffect(() => {
    if (!progressState.active || progressState.phase !== "processing") return undefined;
    const timer = window.setInterval(() => {
      setProgressState((current) => {
        if (!current.active || current.phase !== "processing") return current;
        const elapsed = Date.now() - current.startedAt;
        const estimate = estimateDiacriticsDuration(current.textLength);
        const eased = 1 - Math.exp(-(elapsed / estimate) * 3);
        const nextProgress = Math.min(95, Math.round(6 + eased * 89));
        if (nextProgress <= current.progress) return current;
        return { ...current, progress: nextProgress };
      });
    }, 180);
    return () => window.clearInterval(timer);
  }, [progressState.active, progressState.phase, progressState.startedAt, progressState.textLength]);

  useEffect(() => () => clearCloseTimer(), [clearCloseTimer]);

  return {
    diacriticsProgress: progressState,
    startDiacriticsProgress,
    finishDiacriticsProgress,
    failDiacriticsProgress
  };
}

export function DiacriticsProgressOverlay({ active, progress, phase }) {
  if (!active) return null;
  const complete = phase === "complete";
  return (
    <div className="diacritics-progress-scrim" role="presentation">
      <section className="diacritics-progress-modal" role="dialog" aria-modal="true" aria-labelledby="diacritics-progress-title">
        <div className="diacritics-progress-mark" aria-hidden="true">
          <span>ă</span>
          <span>î</span>
          <span>â</span>
          <span>ș</span>
          <span>ț</span>
        </div>
        <div className="piece-card-kicker">diacritice</div>
        <h2 id="diacritics-progress-title" className="diacritics-progress-title">
          {complete ? "Textul este pregătit" : "Adăugăm diacritice..."}
        </h2>
        <p className="diacritics-progress-copy">
          {complete ? "Aplicăm rezultatul în editor." : "Pentru textele lungi, operațiunea poate dura câteva momente. Nu închide pagina."}
        </p>
        <div className="diacritics-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress} aria-label="Progres estimat diacritice">
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="diacritics-progress-percent" aria-live="polite">Estimare {progress}%</div>
      </section>
    </div>
  );
}

export function useDiacriticsQuota(user) {
  const [quota, setQuota] = useState(null);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const [quotaError, setQuotaError] = useState("");

  const refreshDiacriticsQuota = useCallback(async () => {
    if (!user) {
      setQuota(null);
      setQuotaError("");
      setQuotaLoading(false);
      return null;
    }
    setQuotaLoading(true);
    try {
      const nextQuota = await fetchDiacriticsQuota();
      setQuota(nextQuota);
      setQuotaError("");
      return nextQuota;
    } catch (error) {
      setQuotaError(error.message || "Nu am putut încărca limita pentru Diacritice.");
      return null;
    } finally {
      setQuotaLoading(false);
    }
  }, [user?.id, user?.premium_tier, user?.premium_until]);

  useEffect(() => {
    refreshDiacriticsQuota();
  }, [refreshDiacriticsQuota]);

  const applyDiacriticsQuota = useCallback((nextQuota) => {
    if (nextQuota) setQuota(nextQuota);
  }, []);

  return {
    diacriticsQuota: quota,
    diacriticsQuotaLoading: quotaLoading,
    diacriticsQuotaError: quotaError,
    refreshDiacriticsQuota,
    applyDiacriticsQuota
  };
}

export function DiacriticsControl({
  user,
  enabled,
  onChange,
  disabled = false,
  label = "Adaugă automat diacritice (ăîâțș)?",
  quota = null,
  quotaLoading = false,
  quotaError = ""
}) {
  if (!user) {
    return (
      <p className="diacritics-note">
        Conversia automată la diacritice este disponibilă după autentificare. <a href={mainPath("/premium")}>Vezi Premium</a>
      </p>
    );
  }
  const hasQuota = Boolean(quota);
  const used = Number(quota?.used ?? 0);
  const limit = Number(quota?.limit ?? 0);
  const remaining = Number(quota?.remaining ?? 0);
  const exhausted = hasQuota && remaining <= 0;
  const serviceUnavailable = hasQuota && quota.service_available === false;
  const unavailable = hasQuota && quota.can_request === false;
  const controlDisabled = disabled || quotaLoading || unavailable;

  return (
    <>
      <label className="diacritics-control">
        <input
          type="checkbox"
          checked={enabled}
          disabled={controlDisabled}
          onChange={(event) => onChange(event.target.checked)}
        />
        <span>{label}</span>
      </label>
      <p className={`diacritics-note ${exhausted ? "danger" : ""}`}>
        {quotaLoading && !hasQuota ? "Se încarcă limita pentru Diacritice..." : hasQuota ? (
          <>
            {serviceUnavailable ? (quota.service_unavailable_reason || "Diacriticele sunt indisponibile momentan.") : unavailable && !exhausted ? "Diacriticele sunt indisponibile momentan." : (
              <>
                Diacritice: {formatNumber(used)} / {formatNumber(limit)} caractere folosite.
                {" "}Disponibil: {formatNumber(remaining)} caractere
                {quota.period_end ? ` până la ${formatDateTime(quota.period_end)}` : ""}.
              </>
            )}
          </>
        ) : "Limita pentru Diacritice se verifică la trimitere."}
      </p>
      {quotaError ? <p className="diacritics-note danger">{quotaError}</p> : null}
    </>
  );
}
export function DiacriticsReviewPanel({ active, changed, onReset }) {
  if (!active) return null;
  return (
    <div className="diacritics-review">
      <p>{changed ? "Am pregătit versiunea cu diacritice. Verifică textul, editează ce vrei, apoi trimite." : "Textul pare deja să aibă diacriticele potrivite. Verifică-l și trimite când e gata."}</p>
      {onReset ? (
        <button className="cal-btn" type="button" onClick={onReset}>
          Revino la varianta inițială
        </button>
      ) : null}
    </div>
  );
}
export function diacriticsSubmitLabel({ submitting, reviewing, enabled, submitLabel }) {
  if (submitting) return enabled && !reviewing ? "Se adaugă diacritice..." : "Se trimite...";
  if (reviewing) return submitLabel;
  if (enabled) return "Verifică diacriticele";
  return submitLabel;
}

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { FaGoogle } from "react-icons/fa";
import { PiCubeFill } from "react-icons/pi";
import { AUTH_GOOGLE_PATH, activatePasswordSignup, loginWithPassword, registerWithPassword } from "../api/auth.js";
import { mainPath } from "./paths.js";

// Must match PasswordRegisterRequest.password min_length in app/schemas/users.py.
const MIN_SIGNUP_PASSWORD_LENGTH = 10;

const AuthModalContext = createContext({
  openAuthModal: null
});

export function AuthModalProvider({ value, children }) {
  return <AuthModalContext.Provider value={value}>{children}</AuthModalContext.Provider>;
}

export function useAuthModal() {
  return useContext(AuthModalContext);
}

function providerHref(path, returnTo) {
  if (!returnTo) return path;
  const query = new URLSearchParams({ return_to: returnTo });
  return `${path}?${query.toString()}`;
}

function navigateToAuthReturn(destination) {
  window.location.href = destination || mainPath("/");
}

function referralCodeFromLocation() {
  return new URLSearchParams(window.location.search).get("ref")?.trim() || "";
}

export function AuthLoginModal({ open, returnTo, onClose, onAuthenticated }) {
  const formRef = useRef(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [activationCode, setActivationCode] = useState("");
  const [activationEmail, setActivationEmail] = useState("");
  const [status, setStatus] = useState("");
  const [statusKind, setStatusKind] = useState("error");
  const [busyAction, setBusyAction] = useState("");

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return undefined;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      setEmail("");
      setPassword("");
      setActivationCode("");
      setActivationEmail("");
      setStatus("");
      setStatusKind("error");
      setBusyAction("");
    }
  }, [open]);

  if (!open) return null;

  const submitLogin = async (event) => {
    event.preventDefault();
    if (busyAction) return;
    setBusyAction("login");
    setStatus("");
    setStatusKind("error");
    try {
      const response = await loginWithPassword({ email, password, return_to: returnTo || "" });
      await onAuthenticated?.();
      navigateToAuthReturn(response.redirect_url || returnTo || mainPath("/"));
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut autentifica acest cont.");
      setBusyAction("");
    }
  };

  const submitRegistration = async () => {
    if (busyAction || !formRef.current?.reportValidity()) return;
    if (password.length < MIN_SIGNUP_PASSWORD_LENGTH) {
      setStatusKind("error");
      setStatus(`Parola pentru un cont nou trebuie să aibă cel puțin ${MIN_SIGNUP_PASSWORD_LENGTH} caractere.`);
      return;
    }
    setBusyAction("register");
    setStatus("");
    setStatusKind("error");
    try {
      const referralCode = referralCodeFromLocation();
      const response = await registerWithPassword({
        email,
        password,
        ...(referralCode ? { referral_code: referralCode } : {})
      });
      setActivationEmail(response.email || email);
      setActivationCode("");
      setStatus(response.message || "Ți-am trimis un cod de activare pe email.");
      setStatusKind("success");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut crea contul.");
    } finally {
      setBusyAction("");
    }
  };

  const submitActivation = async () => {
    if (busyAction || !activationCode.trim()) return;
    setBusyAction("activate");
    setStatus("");
    setStatusKind("error");
    try {
      const response = await activatePasswordSignup({ email: activationEmail || email, code: activationCode.trim() });
      window.location.href = response.setup_url || mainPath("/autentificare/configurare");
    } catch (requestError) {
      setStatus(requestError.message || "Nu am putut verifica acest cod.");
      setBusyAction("");
    }
  };

  return (
    <div className="auth-modal-scrim" role="presentation" onClick={onClose}>
      <section className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title" onClick={(event) => event.stopPropagation()}>
        <button className="auth-modal-close" type="button" aria-label="Închide" onClick={onClose}>x</button>
        <div className="piece-card-kicker">cont</div>
        <h2 id="auth-modal-title" className="auth-modal-title">Cont utilizator</h2>
        <p className="auth-modal-copy">
          Dacă ai deja un cont, te poți loga aici cu datele tale. Dacă nu ai cont, introdu adresa de e-mail dorită și o parolă de cel puțin 10 caractere și apasă pe Creează cont. Alternativ, te poți loga prin Google.
        </p>
        <form ref={formRef} className="auth-modal-form" onSubmit={submitLogin}>
          <input
            id="auth-modal-email"
            className="cal-input"
            type="email"
            aria-label="Email"
            placeholder="Email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
            autoFocus
          />
          <div className="auth-modal-password-row">
            <input
              id="auth-modal-password"
              className="cal-input"
              type="password"
              aria-label="Parolă"
              placeholder="Parolă"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
            <button className="cal-btn primary auth-modal-submit" type="submit" disabled={Boolean(busyAction)}>
              {busyAction === "login" ? "Se autentifică..." : "Intră în cont"}
            </button>
          </div>
          {activationEmail ? (
            <div className="auth-modal-code-row">
              <input
                className="cal-input auth-code-input"
                type="text"
                inputMode="numeric"
                aria-label="Cod de activare"
                placeholder="Cod email"
                value={activationCode}
                onChange={(event) => setActivationCode(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    submitActivation();
                  }
                }}
                autoComplete="one-time-code"
              />
              <button className="cal-btn auth-modal-verify" type="button" onClick={submitActivation} disabled={Boolean(busyAction) || !activationCode.trim()}>
                {busyAction === "activate" ? "Se verifică..." : "Verifică"}
              </button>
            </div>
          ) : null}
          {status ? <div className={statusKind === "success" ? "inline-status" : "inline-error"}>{status}</div> : null}
          <div className="auth-modal-action-row">
            <button className="cal-btn auth-modal-create" type="button" onClick={submitRegistration} disabled={Boolean(busyAction)}>
              <PiCubeFill className="auth-modal-create-logo" aria-hidden="true" />
              {busyAction === "register" ? "Se trimite..." : "Creează cont"}
            </button>
            <a className="cal-btn auth-provider google" href={providerHref(AUTH_GOOGLE_PATH, returnTo)}>
              <FaGoogle aria-hidden="true" /> Google
            </a>
          </div>
        </form>
      </section>
    </div>
  );
}

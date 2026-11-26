export class ApiError extends Error {
  constructor(status, message, cause) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.cause = cause;
  }
}

// FastAPI validation errors (422) send `detail` as a list of objects; turn any
// non-string detail into readable text instead of "[object Object]".
export function errorDetailMessage(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => (typeof item === "string" ? item : item?.msg))
      .filter(Boolean);
    return parts.length ? parts.join(" ") : "";
  }
  if (detail && typeof detail === "object") {
    return typeof detail.message === "string" ? detail.message : "";
  }
  return "";
}

export async function request(path, options = {}) {
  const headers = {
    Accept: "application/json",
    ...options.headers
  };

  let body = options.body;
  if (body && typeof body === "object" && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(path, {
      credentials: "include",
      ...options,
      headers,
      body
    });
  } catch (error) {
    const message = error?.name === "AbortError"
      ? "Cererea a fost întreruptă."
      : "Nu am putut contacta serverul. Verifică conexiunea și încearcă din nou.";
    throw new ApiError(0, message, error);
  }

  if (!response.ok) {
    const text = await response.text();
    let message = text || `Cererea a eșuat (${response.status}).`;
    try {
      const json = JSON.parse(text);
      message = errorDetailMessage(json.detail) || errorDetailMessage(json.message) || `Cererea a eșuat (${response.status}).`;
    } catch {
      // Keep the server response text.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new ApiError(
      response.status,
      "Serverul a răspuns cu pagina aplicației în loc de date JSON. Reîncarcă pagina."
    );
  }

  try {
    return await response.json();
  } catch {
    throw new ApiError(response.status, "Răspunsul serverului nu a fost JSON valid.");
  }
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  put: (path, body) => request(path, { method: "PUT", body }),
  delete: (path, body) => request(path, { method: "DELETE", body })
};

export function buildQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const text = query.toString();
  return text ? `?${text}` : "";
}

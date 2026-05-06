export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
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

  const response = await fetch(path, {
    credentials: "include",
    ...options,
    headers,
    body
  });

  if (!response.ok) {
    const text = await response.text();
    let message = text || `Cererea a eșuat (${response.status}).`;
    try {
      const json = JSON.parse(text);
      message = json.detail ?? json.message ?? message;
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

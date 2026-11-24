// API Client connecting to FastAPI backend with mock fallback for standalone demo

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("originality_token");
}

export function setToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("originality_token", token);
  }
}

export function removeToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("originality_token");
  }
}

async function request(endpoint: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const errorText = await res.text();
    let msg = `HTTP ${res.status}`;
    try {
      const parsed = JSON.parse(errorText);
      msg = parsed.detail || msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export async function login(email: string, password: string) {
  return request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function register(email: string, password: string, fullName: string) {
  return request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
}

export async function getMe() {
  return request("/auth/me");
}

export async function getAssignments() {
  return request("/assignments");
}

export async function createAssignment(title: string, className: string, description?: string) {
  return request("/assignments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, class_name: className, description }),
  });
}

export async function uploadSubmission(assignmentId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/assignments/${assignmentId}/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    throw new Error(`Upload failed: ${res.statusText}`);
  }
  return res.json();
}

export async function getSubmissionStatus(submissionId: string) {
  return request(`/submissions/${submissionId}/status`);
}

export async function getReport(submissionId: string) {
  return request(`/submissions/${submissionId}/report`);
}

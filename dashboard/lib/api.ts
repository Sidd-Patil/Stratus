// Public surface (Render) — invite creation, login, join page script delivery.
export const PUBLIC_BASE = process.env.NEXT_PUBLIC_CONTROLLER_URL ?? "http://localhost:8080";
// Internal surface (Tailscale VM) — nodes, events, heartbeat, future job API.
// Users' browsers reach this directly because they're on the tailnet.
export const INTERNAL_BASE = process.env.NEXT_PUBLIC_INTERNAL_CONTROLLER_URL ?? "http://localhost:8081";

export interface CallerInfo {
  role: "admin" | "user";
  identity: string;
}

export interface Node {
  name: string;
  owner: string | null;
  os: string;
  tailscale_ip: string | null;
  cpu_free_pct: number;
  ram_free_mb: number;
  container_state: string;
  last_seen: string;
  status: "online" | "offline";
  created_at: string;
}

export interface InviteRequest {
  node_name: string;
  controller_url: string;
  admin_password: string;
  idle_threshold_s?: number;
  cpu_idle_threshold_pct?: number;
  cpu_cap_active?: number;
  cpu_cap_idle?: number;
  heartbeat_secs?: number;
}

export interface InviteResponse {
  token: string;
  node_name: string;
  join_url: string;
  expires_at: string;
}

export interface JoinData {
  node_name: string;
  agent_config: Record<string, unknown>;
  message: string;
}

function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("dashboard_token") ?? "";
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
}

export async function login(password: string): Promise<string> {
  const res = await fetch(`${PUBLIC_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (res.status === 401) throw new Error("Invalid password.");
  if (!res.ok) throw new Error("Login failed.");
  const data = await res.json();
  localStorage.setItem("dashboard_token", data.token);
  return data.token;
}

export function logout(): void {
  localStorage.removeItem("dashboard_token");
}

export async function fetchNodes(): Promise<Node[]> {
  const res = await fetch(`${INTERNAL_BASE}/api/v1/nodes`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  if (res.status === 401) throw new Error("UNAUTHORIZED");
  if (!res.ok) throw new Error("Failed to fetch nodes");
  return res.json();
}

export async function createInvite(body: InviteRequest): Promise<InviteResponse> {
  const res = await fetch(`${PUBLIC_BASE}/api/v1/invites`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to create invite");
  return res.json();
}

export async function deleteNode(name: string, adminPassword: string): Promise<void> {
  const res = await fetch(`${INTERNAL_BASE}/api/v1/nodes/${encodeURIComponent(name)}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ admin_password: adminPassword }),
  });
  if (res.status === 401) throw new Error("Wrong admin password.");
  if (res.status === 404) throw new Error("Node not found.");
  if (!res.ok) throw new Error("Failed to delete node.");
}

export async function fetchMe(): Promise<CallerInfo> {
  const res = await fetch(`${INTERNAL_BASE}/api/v1/me`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  if (res.status === 401) throw new Error("UNAUTHORIZED");
  if (!res.ok) throw new Error("Failed to identify caller");
  return res.json();
}

export async function fetchJoinData(token: string): Promise<JoinData> {
  const res = await fetch(`${PUBLIC_BASE}/join/${token}`);
  if (res.status === 404) throw new Error("Invite not found");
  if (res.status === 410) throw new Error("Invite expired or already used");
  if (!res.ok) throw new Error("Failed to load invite");
  return res.json();
}

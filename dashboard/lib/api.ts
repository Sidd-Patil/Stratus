const BASE = process.env.NEXT_PUBLIC_CONTROLLER_URL ?? "http://localhost:8080";

export interface Node {
  name: string;
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
  idle_threshold_s?: number;
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

export async function fetchNodes(): Promise<Node[]> {
  const res = await fetch(`${BASE}/api/v1/nodes`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch nodes");
  return res.json();
}

export async function createInvite(body: InviteRequest): Promise<InviteResponse> {
  const res = await fetch(`${BASE}/api/v1/invites`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to create invite");
  return res.json();
}

export async function fetchJoinData(token: string): Promise<JoinData> {
  const res = await fetch(`${BASE}/join/${token}`);
  if (res.status === 404) throw new Error("Invite not found");
  if (res.status === 410) throw new Error("Invite expired or already used");
  if (!res.ok) throw new Error("Failed to load invite");
  return res.json();
}

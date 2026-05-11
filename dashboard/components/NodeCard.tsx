"use client";

import { useState } from "react";
import { Node, deleteNode } from "@/lib/api";

const STATE_LABELS: Record<string, { label: string; color: string }> = {
  running_full:     { label: "Full",     color: "bg-indigo-500/20 text-indigo-300" },
  running_throttle: { label: "Throttled", color: "bg-yellow-500/20 text-yellow-300" },
  paused:           { label: "Paused",   color: "bg-slate-500/20 text-slate-400" },
  unknown:          { label: "Unknown",  color: "bg-slate-500/20 text-slate-400" },
};

function Bar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-slate-700">
      <div
        className={`h-1.5 rounded-full transition-all duration-500 ${color}`}
        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
      />
    </div>
  );
}

function timeAgo(iso: string): string {
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}

export default function NodeCard({ node, onDelete }: { node: Node; onDelete?: () => void }) {
  const online = node.status === "online";
  const state = STATE_LABELS[node.container_state] ?? STATE_LABELS.unknown;
  const ramGB = (node.ram_free_mb / 1024).toFixed(1);

  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteNode(node.name, password);
      onDelete?.();
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Failed to delete.");
      setDeleting(false);
    }
  }

  return (
    <div className="rounded-xl bg-slate-800 border border-slate-700 p-5 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${online ? "bg-green-400" : "bg-slate-500"}`}
            />
            <span className="font-semibold text-white text-lg leading-none">
              {node.name}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 ml-4">{node.os}</p>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${state.color}`}>
          {state.label}
        </span>
      </div>

      {/* Resource bars */}
      <div className="flex flex-col gap-3">
        <div>
          <div className="flex justify-between text-xs text-slate-400 mb-1.5">
            <span>CPU free</span>
            <span>{node.cpu_free_pct.toFixed(1)}%</span>
          </div>
          <Bar pct={node.cpu_free_pct} color="bg-indigo-500" />
        </div>
        <div>
          <div className="flex justify-between text-xs text-slate-400 mb-1.5">
            <span>RAM free</span>
            <span>{ramGB} GB</span>
          </div>
          {/* Treat 16 GB as 100% for the bar */}
          <Bar pct={(node.ram_free_mb / (16 * 1024)) * 100} color="bg-violet-500" />
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <div className="relative group">
          <span className="cursor-default select-none">...</span>
          <div className="absolute bottom-full left-0 mb-1.5 px-2 py-1 bg-slate-700 text-slate-300 rounded text-xs opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
            {node.tailscale_ip ?? "no tailscale ip"}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span>{online ? timeAgo(node.last_seen) : "offline"}</span>
          {!confirming && (
            <button
              onClick={() => setConfirming(true)}
              className="text-slate-600 hover:text-red-400 transition-colors"
              title="Remove node"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Delete confirmation */}
      {confirming && (
        <div className="border-t border-slate-700 pt-3 flex flex-col gap-2">
          <p className="text-xs text-slate-400">Enter admin password to remove <span className="text-white">{node.name}</span>:</p>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleDelete()}
            placeholder="Admin password"
            className="bg-slate-900 border border-slate-600 rounded px-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-red-500"
            autoFocus
          />
          {deleteError && <p className="text-xs text-red-400">{deleteError}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleDelete}
              disabled={deleting || !password}
              className="flex-1 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded transition-colors"
            >
              {deleting ? "Removing…" : "Remove"}
            </button>
            <button
              onClick={() => { setConfirming(false); setPassword(""); setDeleteError(null); }}
              className="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium px-3 py-1.5 rounded transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

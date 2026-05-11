"use client";

import { useEffect, useState } from "react";
import { fetchNodes, Node } from "@/lib/api";
import NodeCard from "@/components/NodeCard";
import InviteModal from "@/components/InviteModal";

const REFRESH_INTERVAL = 15_000;

export default function Dashboard() {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInvite, setShowInvite] = useState(false);

  async function load() {
    try {
      const data = await fetchNodes();
      setNodes(data);
      setError(null);
    } catch {
      setError("Cannot reach controller — is it running?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, []);

  const online = nodes.filter((n) => n.status === "online").length;

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-bold text-xl tracking-tight">Stratus</span>
          {!loading && (
            <span className="text-xs text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
              {online} / {nodes.length} online
            </span>
          )}
        </div>
        <button
          onClick={() => setShowInvite(true)}
          className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          + Invite a Friend
        </button>
      </header>

      <main className="px-6 py-8 max-w-5xl mx-auto">
        {loading && (
          <p className="text-slate-400 text-sm">Connecting to controller…</p>
        )}

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {!loading && !error && nodes.length === 0 && (
          <div className="text-center py-24 text-slate-500">
            <p className="text-lg">No nodes yet.</p>
            <p className="text-sm mt-1">Start the agent on a machine, or invite a friend.</p>
          </div>
        )}

        {nodes.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {nodes.map((node) => (
              <NodeCard key={node.name} node={node} />
            ))}
          </div>
        )}
      </main>

      {showInvite && <InviteModal onClose={() => setShowInvite(false)} />}
    </div>
  );
}

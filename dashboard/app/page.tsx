"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchNodes, fetchMe, logout, Node, CallerInfo } from "@/lib/api";
import NodeCard from "@/components/NodeCard";
import InviteModal from "@/components/InviteModal";

const REFRESH_INTERVAL = 15_000;

export default function Dashboard() {
  const router = useRouter();
  const [caller, setCaller] = useState<CallerInfo | null>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInvite, setShowInvite] = useState(false);

  async function loadNodes() {
    try {
      const data = await fetchNodes();
      setNodes(data);
      setError(null);
    } catch (e) {
      if (e instanceof Error && e.message === "UNAUTHORIZED") {
        router.push("/login");
        return;
      }
      setError("Cannot reach controller — are you on the Tailscale network?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval> | null = null;

    fetchMe()
      .then(info => {
        setCaller(info);
        loadNodes();
        intervalId = setInterval(loadNodes, REFRESH_INTERVAL);
      })
      .catch(e => {
        if (e instanceof Error && e.message === "UNAUTHORIZED") {
          router.push("/login");
          return;
        }
        setError("Cannot reach controller — are you on the Tailscale network?");
        setLoading(false);
      });

    return () => { if (intervalId) clearInterval(intervalId); };
  }, []);

  const isAdmin = caller?.role === "admin";
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
        <div className="flex items-center gap-2">
          {isAdmin && (
            <button
              onClick={() => setShowInvite(true)}
              className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              + Invite a Friend
            </button>
          )}
          {isAdmin && (
            <button
              onClick={() => { logout(); router.push("/login"); }}
              className="text-slate-400 hover:text-white text-sm px-3 py-2 rounded-lg transition-colors"
            >
              Sign out
            </button>
          )}
          {!isAdmin && caller && (
            <span className="text-xs text-slate-500">{caller.identity}</span>
          )}
        </div>
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
            <p className="text-sm mt-1">
              {isAdmin
                ? "Start the agent on a machine, or invite a friend."
                : "Your machines will appear here once the agent is running."}
            </p>
          </div>
        )}

        {nodes.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {nodes.map((node) => (
              <NodeCard key={node.name} node={node} onDelete={loadNodes} isAdmin={isAdmin} />
            ))}
          </div>
        )}
      </main>

      {showInvite && <InviteModal onClose={() => setShowInvite(false)} />}
    </div>
  );
}

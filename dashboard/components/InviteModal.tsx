"use client";

import { useState } from "react";
import { createInvite, InviteResponse } from "@/lib/api";

const CONTROLLER_URL = process.env.NEXT_PUBLIC_CONTROLLER_URL ?? "http://localhost:8080";

export default function InviteModal({ onClose }: { onClose: () => void }) {
  const [nodeName, setNodeName] = useState("");
  const [result, setResult] = useState<InviteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!nodeName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const invite = await createInvite({
        node_name: nodeName.trim().toLowerCase().replace(/\s+/g, "-"),
        controller_url: CONTROLLER_URL,
      });
      setResult(invite);
    } catch {
      setError("Couldn't create invite — is the controller running?");
    } finally {
      setLoading(false);
    }
  }

  function handleCopy() {
    if (!result) return;
    navigator.clipboard.writeText(result.join_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-white font-semibold text-lg">Invite a Friend</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            ✕
          </button>
        </div>

        {!result ? (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1.5">
                What should we call their machine?
              </label>
              <input
                type="text"
                placeholder="e.g. alex-macbook"
                value={nodeName}
                onChange={(e) => setNodeName(e.target.value)}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 text-sm"
                autoFocus
              />
              <p className="text-xs text-slate-500 mt-1">
                Lowercase, no spaces — this is how it appears in the dashboard.
              </p>
            </div>

            {error && <p className="text-red-400 text-sm">{error}</p>}

            <button
              type="submit"
              disabled={loading || !nodeName.trim()}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium py-2 rounded-lg transition-colors text-sm"
            >
              {loading ? "Generating…" : "Generate Invite Link"}
            </button>
          </form>
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-slate-300">
              Send this link to <span className="text-white font-medium">{result.node_name}</span>.
              It expires in 7 days.
            </p>
            <div className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-indigo-300 text-sm font-mono break-all">
              {result.join_url}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCopy}
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2 rounded-lg transition-colors text-sm"
              >
                {copied ? "Copied!" : "Copy Link"}
              </button>
              <button
                onClick={onClose}
                className="flex-1 bg-slate-700 hover:bg-slate-600 text-white font-medium py-2 rounded-lg transition-colors text-sm"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

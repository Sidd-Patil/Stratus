import { fetchJoinData } from "@/lib/api";
import CopyButton from "@/components/CopyButton";

interface Props {
  params: Promise<{ token: string }>;
}

export default async function JoinPage({ params }: Props) {
  const { token } = await params;

  let data;
  let errorMsg: string | null = null;

  try {
    data = await fetchJoinData(token);
  } catch (e) {
    errorMsg = e instanceof Error ? e.message : "Something went wrong";
  }

  if (errorMsg) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-6">
        <div className="max-w-md text-center">
          <p className="text-4xl mb-4">🔗</p>
          <h1 className="text-xl font-semibold mb-2">Link unavailable</h1>
          <p className="text-slate-400 text-sm">{errorMsg}</p>
          <p className="text-slate-500 text-sm mt-2">
            Ask the person who invited you to generate a new link.
          </p>
        </div>
      </div>
    );
  }

  const configJson = JSON.stringify(data!.agent_config, null, 2);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="max-w-2xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-10">
          <p className="text-indigo-400 text-sm font-medium mb-1">You&apos;re invited</p>
          <h1 className="text-3xl font-bold tracking-tight">Join Stratus</h1>
          <p className="text-slate-400 mt-2">
            Your machine will be called{" "}
            <span className="text-white font-medium">{data!.node_name}</span>.
            Follow the steps below to connect.
          </p>
        </div>

        {/* Steps */}
        <div className="flex flex-col gap-6">
          <Step number={1} title="Install Docker">
            <p className="text-slate-400 text-sm">
              Download and install{" "}
              <a
                href="https://orbstack.dev"
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-400 hover:underline"
              >
                OrbStack
              </a>{" "}
              (recommended) or{" "}
              <a
                href="https://docs.docker.com/desktop/mac/install/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-400 hover:underline"
              >
                Docker Desktop
              </a>
              . Make sure it&apos;s running before you continue.
            </p>
          </Step>

          <Step number={2} title="Download the Stratus agent">
            <p className="text-slate-400 text-sm">
              Download the agent binary and place it somewhere on your PATH, like{" "}
              <code className="text-slate-300 bg-slate-800 px-1 rounded">/usr/local/bin/stratus</code>.
            </p>
            <p className="text-slate-500 text-xs mt-2">
              (Binary releases coming soon — ask the person who invited you for the binary for now.)
            </p>
          </Step>

          <Step number={3} title="Save your config file">
            <p className="text-slate-400 text-sm mb-3">
              Save the following as{" "}
              <code className="text-slate-300 bg-slate-800 px-1 rounded">agent.json</code>{" "}
              in the same folder as the agent binary.
            </p>
            <pre className="bg-slate-900 border border-slate-700 rounded-lg p-4 text-sm text-indigo-300 font-mono overflow-x-auto">
              {configJson}
            </pre>
            <CopyButton text={configJson} label="Copy config" />
          </Step>

          <Step number={4} title="Run the agent">
            <p className="text-slate-400 text-sm mb-3">Open a terminal and run:</p>
            <pre className="bg-slate-900 border border-slate-700 rounded-lg p-4 text-sm text-indigo-300 font-mono">
              ./stratus
            </pre>
            <p className="text-slate-500 text-xs mt-2">
              Your machine will appear in the dashboard within 15 seconds.
            </p>
          </Step>
        </div>
      </div>
    </div>
  );
}

function Step({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-4">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-sm font-bold">
        {number}
      </div>
      <div className="flex-1 pt-1">
        <h2 className="font-semibold text-white mb-2">{title}</h2>
        {children}
      </div>
    </div>
  );
}


import { useEffect, useState } from "react";
import { getUserRemediation } from "../lib/api";

export default function RemediationPanel({ employeeId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copiedStep, setCopiedStep] = useState(null);

  useEffect(() => {
    if (!employeeId) return;
    setLoading(true);
    setError(null);
    getUserRemediation(employeeId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [employeeId]);

  function copyCommand(cmd, idx) {
    navigator.clipboard?.writeText(cmd).then(() => {
      setCopiedStep(idx);
      setTimeout(() => setCopiedStep(null), 1500);
    });
  }

  if (!employeeId) {
    return (
      <div className="h-full flex items-center justify-center text-ink-faint text-sm font-mono p-6 text-center">
        Select an identity to see its remediation playbook.
      </div>
    );
  }

  if (loading) {
    return <div className="p-6 text-ink-dim text-sm font-mono">Building playbook…</div>;
  }

  if (error) {
    return <div className="p-6 text-risk-critical text-sm font-mono">{error}</div>;
  }

  return (
    <div className="h-full overflow-auto p-4 space-y-3">
      <div className="border border-bg-line rounded-lg bg-bg-raised p-3">
        <div className="text-[11px] uppercase tracking-wide text-ink-faint font-mono mb-1">Summary</div>
        <p className="text-sm text-ink leading-relaxed"> {data?.summary ?? "No remediation available"}
</p>
      </div>

      <div className="space-y-2">
        {(data?.steps ?? []).map((step, idx) => (
          <div key={idx} className="border border-bg-line rounded-lg bg-bg-panel p-3">
            <div className="flex items-start gap-2.5">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-bg-raised border border-bg-line text-[11px] font-mono flex items-center justify-center text-ink-dim mt-0.5">
                {step.order}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-ink leading-relaxed">{step.description}</p>
                {step.command && (
                  <div className="mt-2 relative group">
                    <pre className="bg-bg text-signal text-[11px] font-mono rounded border border-bg-line px-2.5 py-2 overflow-x-auto whitespace-pre-wrap break-all">
                      {step.command}
                    </pre>
                    <button
                      onClick={() => copyCommand(step.command, idx)}
                      className="absolute top-1.5 right-1.5 text-[10px] font-mono px-1.5 py-0.5 rounded bg-bg-raised border border-bg-line text-ink-faint hover:text-ink hover:border-ink-faint transition-colors"
                    >
                      {copiedStep === idx ? "copied" : "copy"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

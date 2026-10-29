import { CheckCircle2, Cpu, HardDrive, RefreshCw, ServerCrash, XCircle } from "lucide-react";
import { Badge, Button, Card, PageHeader, Stat } from "../components/ui";
import { useHealth } from "../hooks/useHealth";

export default function Status() {
  const { health, checkedAt, refresh } = useHealth();

  return (
    <>
      <PageHeader
        title="System status"
        description="Live readiness of the ForgeGuard inference server, reported by GET /api/health/."
        actions={
          <Button variant="secondary" onClick={refresh} loading={health.state === "loading"}>
            <RefreshCw className="size-4" /> Re-check
          </Button>
        }
      />

      {health.state === "offline" ? (
        <Card className="p-8">
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="grid size-12 shrink-0 place-items-center rounded-xl bg-critical-soft text-critical-ink">
              <ServerCrash className="size-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-ink">Backend unreachable</h2>
              <p className="mt-1 text-ink-2">{health.error}</p>
              <p className="mt-4 text-sm text-ink-2">Start the Django server from the project root:</p>
              <pre className="mt-2 overflow-x-auto rounded-lg bg-surface-2 p-3 font-mono text-sm text-ink">python manage.py runserver</pre>
            </div>
          </div>
        </Card>
      ) : health.state === "loading" ? (
        <Card className="p-8 text-sm text-ink-2">Checking the server…</Card>
      ) : (
        <div className="space-y-6">
          <Card className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center">
            {health.data.status === "ok" ? (
              <CheckCircle2 className="size-8 shrink-0 text-good" />
            ) : (
              <XCircle className="size-8 shrink-0 text-warning" />
            )}
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-ink">
                {health.data.status === "ok" ? "All systems operational" : "Degraded — a model is missing"}
              </h2>
              <p className="text-sm text-ink-2">
                {health.data.status === "ok"
                  ? "Both detection models are loaded from disk and ready to serve requests."
                  : "Place the missing weights file in the weights/ directory and restart the server."}
              </p>
            </div>
            {checkedAt && <p className="text-xs text-ink-3">Checked {checkedAt.toLocaleTimeString()}</p>}
          </Card>

          <div className="grid gap-6 md:grid-cols-3">
            <Card className="p-6">
              <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-ink">
                <Cpu className="size-4 text-ink-3" /> Compute
              </div>
              <dl className="space-y-4">
                <Stat label="Device" value={health.data.device.toUpperCase()} />
                <Stat label="GPU" value={health.data.gpu_name ?? "None — running on CPU"} />
              </dl>
              {health.data.device === "cpu" && (
                <p className="mt-4 text-xs text-ink-3">Video analysis is several times faster on a CUDA GPU.</p>
              )}
            </Card>

            {(["image", "video"] as const).map((k) => {
              const m = health.data.models[k];
              return (
                <Card key={k} className="p-6">
                  <div className="mb-4 flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <HardDrive className="size-4 text-ink-3" /> {k === "image" ? "Image model" : "Video model"}
                    </span>
                    {m.present ? <Badge tone="good">Ready</Badge> : <Badge tone="critical">Missing</Badge>}
                  </div>
                  <dl className="space-y-4">
                    <Stat label="Architecture" value={m.name} />
                    <Stat label="Weights" value={<span className="font-mono text-xs">{m.file}</span>} hint={m.present ? `${m.size_mb} MB` : "Not found on disk"} />
                  </dl>
                </Card>
              );
            })}
          </div>

          <Card className="p-6">
            <h3 className="mb-4 text-sm font-semibold text-ink">Upload limits</h3>
            <dl className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Max file size" value={`${health.data.limits.max_upload_mb} MB`} />
              <Stat label="Video frames sampled" value={health.data.limits.video_frames_sampled} />
              <Stat wrap label="Image formats" value={health.data.limits.image_extensions.join(", ")} />
              <Stat wrap label="Video formats" value={health.data.limits.video_extensions.join(", ")} />
            </dl>
          </Card>
        </div>
      )}
    </>
  );
}

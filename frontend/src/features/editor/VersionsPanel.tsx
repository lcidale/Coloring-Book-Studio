// frontend/src/features/editor/VersionsPanel.tsx
import { useState } from "react"
import { useVersions, useRestoreVersion, useUpdateVersion, useDeleteVersion, useUseVersionAsReference, pageImageSrc } from "@/lib/api"
import { Button } from "@/components/ui/button"

export function VersionsPanel({ pageId, onCopyPrompt }: { pageId: string; onCopyPrompt: (prompt: string) => void }) {
  const { data: versions = [], isLoading } = useVersions(pageId)
  const restore = useRestoreVersion(pageId)
  const update = useUpdateVersion(pageId)
  const del = useDeleteVersion(pageId)
  const useAsReference = useUseVersionAsReference(pageId)
  const [expanded, setExpanded] = useState<string | null>(null)

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading versions…</p>
  if (versions.length === 0) return <p className="text-sm text-muted-foreground">No versions yet — generate to create v1.</p>

  return (
    <div className="space-y-3">
      {versions.map((v) => (
        <div key={v.id} className="rounded-lg border p-3">
          <div className="flex items-start gap-3">
            {v.image_url && (
              <img src={pageImageSrc(v.image_url)} alt={`v${v.version_num}`} className="h-20 w-16 object-contain border" />
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium">v{v.version_num}</span>
                {v.is_current && <span className="rounded bg-emerald-100 px-1.5 text-xs text-emerald-700">Current</span>}
                {v.label && <span className="rounded bg-muted px-1.5 text-xs text-muted-foreground">{v.label}</span>}
              </div>
              <input
                aria-label={`Label for v${v.version_num}`}
                defaultValue={v.label ?? ""}
                placeholder="add a label…"
                className="mt-1 w-full bg-transparent text-sm outline-none border-b border-dashed"
                onBlur={(e) => { if (e.target.value !== (v.label ?? "")) update.mutate({ versionId: v.id, label: e.target.value }) }}
              />
              <button
                className="mt-1 text-xs underline text-muted-foreground"
                onClick={() => setExpanded(expanded === v.id ? null : v.id)}
              >{expanded === v.id ? "hide prompt" : "show prompt"}</button>
              {expanded === v.id && (
                <pre className="mt-1 whitespace-pre-wrap text-xs bg-muted p-2 rounded">{v.prompt}</pre>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" aria-label={`Copy prompt from v${v.version_num}`} onClick={() => onCopyPrompt(v.prompt)}>Copy prompt</Button>
                <Button size="sm" variant="outline" disabled={v.is_current || restore.isPending} onClick={() => restore.mutate(v.id)}>Restore as current</Button>
                <Button size="sm" variant="outline" disabled={useAsReference.isPending} onClick={() => useAsReference.mutate(v.id)}>Use as reference</Button>
                <Button size="sm" variant="outline" aria-label={`Delete version v${v.version_num}`} disabled={v.is_current || del.isPending} onClick={() => del.mutate(v.id)}>Delete</Button>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

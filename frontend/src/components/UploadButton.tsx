import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'
import { api } from '../api/client'
import type { UploadResult } from '../api/types'
import { Button, InlineError } from './ui'

export function UploadButton({ endpoint, label, onUploaded }: { endpoint: string; label: string; onUploaded?: (r: UploadResult) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const qc = useQueryClient()
  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData()
      body.append('file', file)
      return api<UploadResult>(endpoint, { method: 'POST', body })
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['documents'] })
      void qc.invalidateQueries({ queryKey: ['collections'] })
      onUploaded?.(r)
    },
  })
  return (
    <div>
      <input
        ref={input}
        type="file"
        accept=".md,.markdown,.txt,text/markdown,text/plain"
        className="hidden"
        data-testid="file-input"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) upload.mutate(file)
          e.target.value = ''
        }}
      />
      <Button onClick={() => input.current?.click()} loading={upload.isPending}>
        {label}
      </Button>
      {upload.data && !upload.data.created && <p className="mt-2 text-sm text-slate-500">No changes: identical to the latest version.</p>}
      <InlineError error={upload.error} />
    </div>
  )
}

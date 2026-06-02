import clsx from 'clsx'
import { FileText, RefreshCw, Trash2, Upload } from 'lucide-react'
import { type DragEvent, type ChangeEvent, useCallback, useEffect, useRef, useState } from 'react'
import { deleteDocument, fetchDocuments, uploadDocuments } from '../../lib/api'
import type { DocumentOut } from '../../lib/types'

const STATUS_STYLES: Record<string, string> = {
  pending:    'bg-gray-100   text-gray-600',
  processing: 'bg-blue-100   text-blue-700',
  indexed:    'bg-green-100  text-green-700',
  failed:     'bg-red-100    text-red-600',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={clsx('rounded-full px-2 py-0.5 text-xs font-medium', STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600')}>
      {status}
    </span>
  )
}

export function DocumentManager() {
  const [docs,      setDocs]      = useState<DocumentOut[]>([])
  const [loading,   setLoading]   = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error,     setError]     = useState<string | null>(null)
  const [dragging,  setDragging]  = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setDocs(await fetchDocuments())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleFiles = async (files: File[]) => {
    if (!files.length) return
    setUploading(true)
    setError(null)
    try {
      const res = await uploadDocuments(files)
      setDocs((prev) => [...res.documents, ...prev])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    handleFiles(Array.from(e.target.files ?? []))
    e.target.value = ''   // reset so the same file can be re-uploaded
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    handleFiles(Array.from(e.dataTransfer.files))
  }

  const onDelete = async (id: string) => {
    try {
      await deleteDocument(id)
      setDocs((prev) => prev.filter((d) => d.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  return (
    <section className="mt-8">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">Knowledge Base Documents</h2>
        <button
          onClick={load}
          title="Refresh"
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-6 py-8 text-sm text-gray-500 transition',
          dragging ? 'border-brand-400 bg-brand-50' : 'border-gray-200 bg-white hover:border-brand-300 hover:bg-gray-50',
        )}
      >
        <Upload className={clsx('h-7 w-7', dragging ? 'text-brand-500' : 'text-gray-400')} />
        <span>
          {uploading
            ? 'Uploading…'
            : 'Drag & drop files here, or click to select'}
        </span>
        <span className="text-xs text-gray-400">PDF, DOCX, HTML, TXT — up to 50 MB each</span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.html,.txt,text/plain,text/html,application/pdf"
          onChange={onInputChange}
          className="hidden"
        />
      </div>

      {error && (
        <p className="mt-3 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>
      )}

      {/* Document list */}
      <div className="mt-4 rounded-2xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        {loading && !docs.length ? (
          <p className="px-4 py-6 text-center text-sm text-gray-400">Loading…</p>
        ) : docs.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-gray-400">No documents yet. Upload one above.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs font-medium text-gray-500">
                <th className="px-4 py-3 text-left">Filename</th>
                <th className="px-4 py-3 text-left">Type</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-right">Chunks</th>
                <th className="px-4 py-3 text-right">Uploaded</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {docs.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50/60 transition">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 shrink-0 text-gray-400" />
                      <span className="truncate max-w-[220px] font-mono text-xs text-gray-700">{doc.filename}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs uppercase text-gray-500">{doc.file_type}</td>
                  <td className="px-4 py-3"><StatusBadge status={doc.status} /></td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-600">{doc.chunk_count}</td>
                  <td className="px-4 py-3 text-right text-xs text-gray-400 whitespace-nowrap">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => onDelete(doc.id)}
                      title="Delete document"
                      className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500 transition"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

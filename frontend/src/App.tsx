import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  BookOpenText,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  FileText,
  Filter,
  LayoutDashboard,
  MessageSquareText,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
  UserCircle2,
} from 'lucide-react'
import {
  API_BASE_URL,
  askQuestion,
  deleteDocument,
  getApiErrorMessage,
  getDocuments,
  uploadDocument,
  type AskResponse,
  type DocumentItem,
} from './services/api'

type ActiveTab = 'dashboard' | 'policies' | 'chat' | 'conversations' | 'settings'
type ConversationEntry = {
  id: string
  documentId: string
  documentName: string
  question: string
  answer: string
  grounded: boolean
  createdAt: string
  citations: AskResponse['citations']
  latency_ms: number
}

const navItems: Array<{ id: ActiveTab; label: string; icon: typeof LayoutDashboard }> = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'policies', label: 'Policies', icon: FileText },
  { id: 'chat', label: 'AI Policy Chat', icon: MessageSquareText },
  { id: 'conversations', label: 'Conversations', icon: Activity },
  { id: 'settings', label: 'Settings', icon: Settings },
]

const formatDate = (value: string): string =>
  new Date(value).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })

const formatDateTime = (value: string): string =>
  new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })

const statusClass = (status: string): string => {
  switch (status) {
    case 'indexed':
      return 'bg-emerald-100 text-emerald-700'
    case 'processing':
      return 'bg-amber-100 text-amber-700'
    case 'failed':
      return 'bg-rose-100 text-rose-700'
    default:
      return 'bg-slate-100 text-slate-700'
  }
}

export default function App() {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<ActiveTab>('dashboard')
  const [searchTerm, setSearchTerm] = useState('')
  const [policyTypeFilter, setPolicyTypeFilter] = useState<'all' | 'pdf' | 'docx'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'indexed' | 'processing' | 'failed'>('all')
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'name'>('newest')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [conversation, setConversation] = useState<{ documentId: string; id: string } | null>(null)
  const [conversationHistory, setConversationHistory] = useState<ConversationEntry[]>([])
  const [conversationFilter, setConversationFilter] = useState<'all' | string>('all')

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedId) ?? documents[0] ?? null,
    [documents, selectedId],
  )

  const summary = useMemo(() => {
    const indexed = documents.filter((document) => document.status === 'indexed').length
    const processing = documents.filter((document) => document.status === 'processing').length
    const failed = documents.filter((document) => document.status === 'failed').length
    const recent = [...documents].sort(
      (left, right) => new Date(right.created_at).valueOf() - new Date(left.created_at).valueOf(),
    )

    return {
      total: documents.length,
      indexed,
      processing,
      failed,
      recent,
      conversations: conversationHistory.length,
    }
  }, [conversationHistory.length, documents])

  const filteredPolicies = useMemo(() => {
    const query = searchTerm.trim().toLowerCase()
    const docs = documents.filter((document) => {
      const matchesQuery = !query || document.filename.toLowerCase().includes(query)
      const matchesType = policyTypeFilter === 'all' || document.file_type === policyTypeFilter
      const matchesStatus = statusFilter === 'all' || document.status === statusFilter
      return matchesQuery && matchesType && matchesStatus
    })

    return [...docs].sort((left, right) => {
      if (sortBy === 'name') {
        return left.filename.localeCompare(right.filename)
      }
      const delta = new Date(right.created_at).valueOf() - new Date(left.created_at).valueOf()
      return sortBy === 'oldest' ? -delta : delta
    })
  }, [documents, policyTypeFilter, searchTerm, sortBy, statusFilter])

  const recentActivity = useMemo(() => {
    const documentEntries = documents.map((document) => ({
      id: `doc-${document.id}`,
      title: `Document indexed: ${document.filename}`,
      subtitle: `${document.file_type.toUpperCase()} • ${document.status}`,
      time: document.created_at,
      tone: 'neutral' as const,
    }))

    const chatEntries = conversationHistory.map((entry) => ({
      id: `chat-${entry.id}`,
      title: `Question answered for ${entry.documentName}`,
      subtitle: entry.question,
      time: entry.createdAt,
      tone: entry.grounded ? ('success' as const) : ('warning' as const),
    }))

    return [...documentEntries, ...chatEntries]
      .sort((left, right) => new Date(right.time).valueOf() - new Date(left.time).valueOf())
      .slice(0, 5)
  }, [conversationHistory, documents])

  const chartValues = useMemo(() => {
    const counts = {
      indexed: documents.filter((document) => document.status === 'indexed').length,
      processing: documents.filter((document) => document.status === 'processing').length,
      failed: documents.filter((document) => document.status === 'failed').length,
    }
    const maxValue = Math.max(1, ...Object.values(counts))

    return [
      { label: 'Indexed', value: counts.indexed, height: `${(counts.indexed / maxValue) * 100}%` },
      { label: 'Processing', value: counts.processing, height: `${(counts.processing / maxValue) * 100}%` },
      { label: 'Failed', value: counts.failed, height: `${(counts.failed / maxValue) * 100}%` },
    ]
  }, [documents])

  const filteredConversations = useMemo(() => {
    const query = searchTerm.trim().toLowerCase()
    return conversationHistory.filter((entry) => {
      const matchesPolicy = conversationFilter === 'all' || entry.documentId === conversationFilter
      const matchesQuery =
        !query ||
        entry.documentName.toLowerCase().includes(query) ||
        entry.question.toLowerCase().includes(query) ||
        entry.answer.toLowerCase().includes(query)
      return matchesPolicy && matchesQuery
    })
  }, [conversationFilter, conversationHistory, searchTerm])

  const loadDocuments = async () => {
    setLoading(true)
    setError(null)

    try {
      const data = await getDocuments()
      setDocuments(data)
      if (!selectedId && data.length > 0) {
        setSelectedId(data[0].id)
      }
      if (selectedId && !data.some((document) => document.id === selectedId)) {
        const nextSelected = data[0]?.id ?? null
        setSelectedId(nextSelected)
        setAnswer(null)
        setConversation(null)
      }
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDocuments()
  }, [])

  const selectDocument = (documentId: string) => {
    if (documentId === selectedId) {
      return
    }
    setSelectedId(documentId)
    setAnswer(null)
    setConversation(null)
    setChatError(null)
  }

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    setUploading(true)
    setUploadError(null)

    try {
      const uploadedDocument = await uploadDocument(file)
      setDocuments((currentDocuments) => [uploadedDocument, ...currentDocuments])
      setSelectedId(uploadedDocument.id)
      setAnswer(null)
      setConversation(null)
      setQuestion('')
      setActiveTab('policies')
    } catch (requestError) {
      setUploadError(getApiErrorMessage(requestError))
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  const handleDelete = async (documentId: string) => {
    try {
      await deleteDocument(documentId)
      const nextDocuments = documents.filter((document) => document.id !== documentId)
      setDocuments(nextDocuments)
      if (selectedId === documentId) {
        setSelectedId(nextDocuments[0]?.id ?? null)
        setAnswer(null)
        setConversation(null)
      }
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    }
  }

  const handleAsk = async (event: FormEvent) => {
    event.preventDefault()

    if (!selectedDocument || !question.trim() || chatLoading) {
      return
    }

    setChatLoading(true)
    setChatError(null)

    try {
      const result = await askQuestion({
        document_id: selectedDocument.id,
        question: question.trim(),
        conversation_id: conversation?.documentId === selectedDocument.id ? conversation.id : null,
      })

      setAnswer(result)
      setConversation({ documentId: selectedDocument.id, id: result.conversation_id })
      setConversationHistory((current) => {
        const existingIndex = current.findIndex((entry) => entry.id === result.conversation_id)
        if (existingIndex >= 0) {
          const updated = [...current]
          updated[existingIndex] = {
            id: result.conversation_id,
            documentId: selectedDocument.id,
            documentName: selectedDocument.filename,
            question: question.trim(),
            answer: result.answer,
            grounded: result.grounded,
            createdAt: new Date().toISOString(),
            citations: result.citations,
            latency_ms: result.latency_ms,
          }
          return updated
        }

        return [
          {
            id: result.conversation_id,
            documentId: selectedDocument.id,
            documentName: selectedDocument.filename,
            question: question.trim(),
            answer: result.answer,
            grounded: result.grounded,
            createdAt: new Date().toISOString(),
            citations: result.citations,
            latency_ms: result.latency_ms,
          },
          ...current,
        ]
      })
      setQuestion('')
      setActiveTab('chat')
    } catch (requestError) {
      setChatError(getApiErrorMessage(requestError))
    } finally {
      setChatLoading(false)
    }
  }

  const renderDashboard = () => (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-violet-600">Overview</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Welcome back</h1>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => setActiveTab('policies')}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm"
          >
            <FileText size={16} />
            View Policies
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('chat')}
            className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm"
          >
            <MessageSquareText size={16} />
            Ask AI
          </button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard label="Total Policies" value={String(summary.total)} caption="Across all uploaded documents" tone="violet" />
        <SummaryCard label="Indexed" value={String(summary.indexed)} caption="Ready for policy Q&A" tone="emerald" />
        <SummaryCard label="Processing" value={String(summary.processing)} caption="Awaiting ingestion" tone="amber" />
        <SummaryCard label="Conversations" value={String(summary.conversations)} caption="AI policy sessions" tone="slate" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.5fr_0.9fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Recent Policies</h2>
              <p className="text-sm text-slate-500">Latest uploads and indexing status</p>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab('policies')}
              className="text-sm font-medium text-violet-600"
            >
              See all
            </button>
          </div>

          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3 font-medium">Policy</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {summary.recent.slice(0, 5).map((document) => (
                  <tr key={document.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{document.filename}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${statusClass(document.status)}`}>
                        {document.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatDate(document.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Indexing status</h2>
              <p className="text-sm text-slate-500">Current document health</p>
            </div>
          </div>

          <div className="flex h-44 items-end gap-4">
            {chartValues.map((item) => (
              <div key={item.label} className="flex flex-1 flex-col items-center gap-2">
                <div className="flex h-28 w-full items-end justify-center rounded-t-xl bg-slate-100 p-2">
                  <div
                    className={`w-full rounded-t-xl ${
                      item.label === 'Indexed'
                        ? 'bg-emerald-500'
                        : item.label === 'Processing'
                          ? 'bg-amber-500'
                          : 'bg-rose-500'
                    }`}
                    style={{ height: item.height }}
                  />
                </div>
                <div className="text-center">
                  <div className="text-xs font-medium text-slate-500">{item.value}</div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{item.label}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Recent activity</h2>
              <p className="text-sm text-slate-500">Latest document and AI interactions</p>
            </div>
          </div>

          <div className="space-y-4">
            {recentActivity.map((entry) => (
              <div key={entry.id} className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div
                  className={`mt-0.5 flex h-9 w-9 items-center justify-center rounded-full ${
                    entry.tone === 'success'
                      ? 'bg-emerald-100 text-emerald-700'
                      : entry.tone === 'warning'
                        ? 'bg-amber-100 text-amber-700'
                        : 'bg-violet-100 text-violet-700'
                  }`}
                >
                  {entry.tone === 'success' ? <CheckCircle2 size={16} /> : entry.tone === 'warning' ? <AlertCircle size={16} /> : <Activity size={16} />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-slate-800">{entry.title}</div>
                  <div className="mt-1 truncate text-sm text-slate-500">{entry.subtitle}</div>
                </div>
                <div className="text-xs text-slate-400">{formatDateTime(entry.time)}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Quick actions</h2>
            </div>
          </div>

          <div className="space-y-3">
            <button
              type="button"
              onClick={() => document.getElementById('upload-input')?.click()}
              className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm font-medium text-slate-700"
            >
              <span className="inline-flex items-center gap-2">
                <UploadCloud size={16} className="text-violet-600" />
                Upload Policy
              </span>
              <ChevronRight size={16} />
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('chat')}
              className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm font-medium text-slate-700"
            >
              <span className="inline-flex items-center gap-2">
                <Sparkles size={16} className="text-violet-600" />
                Ask AI
              </span>
              <ChevronRight size={16} />
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('policies')}
              className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm font-medium text-slate-700"
            >
              <span className="inline-flex items-center gap-2">
                <BookOpenText size={16} className="text-violet-600" />
                View Policies
              </span>
              <ChevronRight size={16} />
            </button>
          </div>
        </section>
      </div>
    </div>
  )

  const renderPolicies = () => (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-violet-600">Policies</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Policy library</h1>
        </div>
        <div className="flex flex-wrap gap-3">
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm">
            <UploadCloud size={16} />
            {uploading ? 'Uploading…' : 'Upload Policy'}
            <input id="upload-input" type="file" accept=".pdf,.docx" className="hidden" onChange={handleUpload} />
          </label>
        </div>
      </div>

      {uploadError ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{uploadError}</div>
      ) : null}

      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-[1.3fr_0.7fr_0.7fr_0.7fr]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search policies"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-3 text-sm text-slate-700 outline-none focus:border-violet-300"
            />
          </div>
          <div className="relative">
            <Filter className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <select
              value={policyTypeFilter}
              onChange={(event) => setPolicyTypeFilter(event.target.value as 'all' | 'pdf' | 'docx')}
              className="w-full appearance-none rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-3 text-sm text-slate-700 outline-none focus:border-violet-300"
            >
              <option value="all">All types</option>
              <option value="pdf">PDF</option>
              <option value="docx">DOCX</option>
            </select>
          </div>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as 'all' | 'indexed' | 'processing' | 'failed')}
            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-violet-300"
          >
            <option value="all">All statuses</option>
            <option value="indexed">Indexed</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
          </select>
          <select
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value as 'newest' | 'oldest' | 'name')}
            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-violet-300"
          >
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
            <option value="name">Name</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white px-5 py-14 text-center text-sm text-slate-500 shadow-sm">
          Loading policies...
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-5 py-14 text-center text-sm text-rose-700 shadow-sm">{error}</div>
      ) : filteredPolicies.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-5 py-16 text-center text-sm text-slate-500 shadow-sm">
          No policies match the current filters.
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-5 py-3 font-medium">Policy</th>
                  <th className="px-5 py-3 font-medium">Type</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Chunks</th>
                  <th className="px-5 py-3 font-medium">Created</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {filteredPolicies.map((document) => (
                  <tr key={document.id} className={selectedDocument?.id === document.id ? 'bg-violet-50/60' : 'bg-white'}>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                          <FileText size={16} />
                        </div>
                        <div>
                          <div className="font-medium text-slate-800">{document.filename}</div>
                          <div className="mt-1 text-xs text-slate-500">v{document.version}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4 uppercase tracking-wide text-slate-500">{document.file_type}</td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${statusClass(document.status)}`}>
                        {document.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-slate-600">{document.chunk_count}</td>
                    <td className="px-5 py-4 text-slate-600">{formatDate(document.created_at)}</td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            selectDocument(document.id)
                            setActiveTab('chat')
                          }}
                          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700"
                        >
                          Open
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            selectDocument(document.id)
                            setActiveTab('chat')
                          }}
                          className="rounded-lg bg-violet-600 px-2.5 py-1.5 text-xs font-medium text-white"
                        >
                          Ask AI
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(document.id)}
                          className="rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-xs font-medium text-rose-700"
                        >
                          <span className="inline-flex items-center gap-1">
                            <Trash2 size={12} />
                            Delete
                          </span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )

  const renderChat = () => (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-violet-600">AI Policy Chat</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Ask about a policy</h1>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.5fr_0.88fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5">
            <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Selected policy</label>
            <select
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-violet-300"
              value={selectedDocument?.id ?? ''}
              onChange={(event) => selectDocument(event.target.value)}
            >
              {documents.map((document) => (
                <option key={document.id} value={document.id}>
                  {document.filename}
                </option>
              ))}
            </select>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            {!answer ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <Sparkles size={16} className="text-violet-600" />
                  Ask a question about the selected policy
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl bg-violet-600 px-4 py-3 text-sm text-white shadow-sm">
                    {question || 'Previous question'}
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="max-w-[90%] rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-700 shadow-sm">
                    <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-violet-600">
                      <ShieldCheck size={14} />
                      Policy answer
                    </div>
                    <p className="whitespace-pre-wrap">{answer.answer}</p>
                  </div>
                </div>
              </div>
            )}
          </div>

          <form className="mt-5 space-y-3" onSubmit={handleAsk}>
            <label className="block text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Question</label>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              rows={5}
              placeholder="Ask a question about the selected policy…"
              className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-violet-300"
            />

            <button
              type="submit"
              disabled={chatLoading || !question.trim() || !selectedDocument}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {chatLoading ? 'Asking…' : 'Ask AI'}
              <ArrowUpRight size={16} />
            </button>
          </form>

          {chatError ? (
            <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{chatError}</div>
          ) : null}
        </section>

        <aside className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Sources</h2>
              <p className="text-sm text-slate-500">Grounded evidence and citations</p>
            </div>
          </div>

          {!answer ? (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
              Submit a question to see document citations here.
            </div>
          ) : answer.grounded && answer.citations.length > 0 ? (
            <div className="space-y-3">
              {answer.citations.map((citation) => (
                <div key={citation.chunk_id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-500">
                    <span>Page {citation.page ?? 'N/A'}</span>
                    <span>{citation.section ?? 'General'}</span>
                  </div>
                  <blockquote className="text-sm leading-6 text-slate-700">“{citation.quote}”</blockquote>
                  <div className="mt-3 text-xs text-violet-700">Relevance score: {citation.relevance_score.toFixed(2)}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-800">
              The selected policy does not provide enough information to answer this question.
            </div>
          )}
        </aside>
      </div>
    </div>
  )

  const renderConversations = () => (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-violet-600">Conversations</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">AI conversation history</h1>
        </div>
        <button
          type="button"
          onClick={() => setActiveTab('chat')}
          className="inline-flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white"
        >
          <MessageSquareText size={16} />
          New chat
        </button>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-[1.2fr_0.8fr]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="text"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search conversations"
              className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-3 text-sm text-slate-700 outline-none focus:border-violet-300"
            />
          </div>
          <select
            value={conversationFilter}
            onChange={(event) => setConversationFilter(event.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700 outline-none focus:border-violet-300"
          >
            <option value="all">All policies</option>
            {documents.map((document) => (
              <option key={document.id} value={document.id}>
                {document.filename}
              </option>
            ))}
          </select>
        </div>
      </div>

      {filteredConversations.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-5 py-16 text-center text-sm text-slate-500 shadow-sm">
          No conversations available yet. Ask a policy question from the AI chat to create one.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredConversations.map((entry) => (
            <div key={entry.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{entry.documentName}</div>
                  <div className="mt-2 text-lg font-semibold text-slate-900">{entry.question}</div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedId(entry.documentId)
                    setAnswer({
                      answer: entry.answer,
                      grounded: entry.grounded,
                      needs_clarification: false,
                      citations: entry.citations,
                      document_id: entry.documentId,
                      conversation_id: entry.id,
                      latency_ms: entry.latency_ms,
                    })
                    setConversation({ documentId: entry.documentId, id: entry.id })
                    setActiveTab('chat')
                  }}
                  className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700"
                >
                  Open conversation
                </button>
              </div>
              <div className="mt-3 text-sm leading-6 text-slate-600">{entry.answer}</div>
              <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                <span>{formatDateTime(entry.createdAt)}</span>
                <span className="h-1 w-1 rounded-full bg-slate-300" />
                <span>{entry.grounded ? 'Grounded answer' : 'Insufficient evidence'}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )

  const renderSettings = () => (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-violet-600">Settings</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">Profile & preferences</h1>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-100 text-violet-700">
              <UserCircle2 size={28} />
            </div>
            <div>
              <div className="text-xl font-semibold text-slate-900">Policy workspace admin</div>
              <div className="text-sm text-slate-500">Local environment</div>
            </div>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <SettingCard label="Workspace" value="Policy Intelligence" />
            <SettingCard label="Environment" value="Docker Compose" />
            <SettingCard label="Frontend" value="http://localhost:8080" />
            <SettingCard label="API" value={API_BASE_URL} />
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Preferences</h2>
          <div className="mt-5 space-y-4">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="text-sm font-medium text-slate-800">Default policy view</div>
              <div className="mt-1 text-sm text-slate-500">Policy library</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="text-sm font-medium text-slate-800">Citations</div>
              <div className="mt-1 text-sm text-slate-500">Always display grounded sources</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="text-sm font-medium text-slate-800">AI behavior</div>
              <div className="mt-1 text-sm text-slate-500">Answer strictly from supplied policy evidence</div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )

  return (
    <main className="min-h-screen bg-[#F6F7FB] text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-[1800px] flex-col lg:flex-row">
        <aside className="w-full border-b border-slate-200 bg-[#0F172A] text-slate-200 lg:w-[250px] lg:border-b-0 lg:border-r lg:border-slate-700">
          <div className="flex h-full flex-col p-5">
            <div className="flex items-center gap-3 px-2 py-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600 text-white shadow-sm">
                <ShieldCheck size={18} />
              </div>
              <div className="text-lg font-semibold text-white">
                Policy<span className="text-slate-400">Intelligence</span>
              </div>
            </div>

            <div className="mt-8 text-[10px] font-bold uppercase tracking-[0.22em] text-slate-400">Workspace</div>
            <nav className="mt-4 space-y-2">
              {navItems.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setActiveTab(id)}
                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition ${
                    activeTab === id
                      ? 'bg-violet-500/15 text-violet-100 ring-1 ring-violet-400/40'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  <Icon size={16} />
                  {label}
                </button>
              ))}
            </nav>

            <div className="mt-auto rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-violet-500/20 font-semibold text-violet-200">
                  PI
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">Policy workspace</div>
                  <div className="text-xs text-slate-400">Secure AI environment</div>
                </div>
              </div>
            </div>
          </div>
        </aside>

        <div className="flex-1">
          <header className="border-b border-slate-200 bg-white/90 backdrop-blur-sm">
            <div className="flex flex-col gap-3 px-5 py-4 sm:px-8 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 lg:w-[480px]">
                <Search size={16} className="text-slate-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search policies and conversations"
                  className="w-full border-0 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
                />
              </div>

              <div className="flex items-center gap-3 self-end lg:self-auto">
                <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  Live API ready
                </div>
                <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-violet-100 text-violet-700">
                    <UserCircle2 size={18} />
                  </div>
                  <div className="hidden text-left sm:block">
                    <div className="text-sm font-medium text-slate-800">Policy admin</div>
                    <div className="text-[11px] text-slate-500">Secure workspace</div>
                  </div>
                </div>
              </div>
            </div>
          </header>

          <div className="p-5 sm:p-8">
            {activeTab === 'dashboard' && renderDashboard()}
            {activeTab === 'policies' && renderPolicies()}
            {activeTab === 'chat' && renderChat()}
            {activeTab === 'conversations' && renderConversations()}
            {activeTab === 'settings' && renderSettings()}
          </div>
        </div>
      </div>
    </main>
  )
}

type SummaryCardProps = {
  label: string
  value: string
  caption: string
  tone: 'violet' | 'emerald' | 'amber' | 'slate'
}

function SummaryCard({ label, value, caption, tone }: SummaryCardProps) {
  const tones = {
    violet: 'bg-violet-100 text-violet-700',
    emerald: 'bg-emerald-100 text-emerald-700',
    amber: 'bg-amber-100 text-amber-700',
    slate: 'bg-slate-100 text-slate-700',
  }

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className={`mb-4 inline-flex rounded-xl p-2 ${tones[tone]}`}>
        {tone === 'violet' ? <BookOpenText size={18} /> : tone === 'emerald' ? <CheckCircle2 size={18} /> : tone === 'amber' ? <BriefcaseBusiness size={18} /> : <MessageSquareText size={18} />}
      </div>
      <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">{label}</div>
      <div className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">{value}</div>
      <div className="mt-1 text-sm text-slate-500">{caption}</div>
    </article>
  )
}

type SettingCardProps = {
  label: string
  value: string
}

function SettingCard({ label, value }: SettingCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</div>
      <div className="mt-2 text-sm font-medium text-slate-800">{value}</div>
    </div>
  )
}



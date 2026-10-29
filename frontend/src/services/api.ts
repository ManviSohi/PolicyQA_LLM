import axios from 'axios'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
const fallbackBaseUrl = '/api'

export const API_BASE_URL = configuredBaseUrl || fallbackBaseUrl

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export type DocumentItem = {
  id: string
  filename: string
  file_type: string
  file_size: number
  sha256: string
  version: number
  status: 'processing' | 'indexed' | 'failed' | string
  page_count: number | null
  chunk_count: number
  created_at: string
  updated_at: string
  error_message: string | null
}

export type CitationItem = {
  chunk_id: string
  page: number | null
  section: string | null
  quote: string
  relevance_score: number
}

export type AskResponse = {
  answer: string
  grounded: boolean
  needs_clarification: boolean
  citations: CitationItem[]
  document_id: string
  conversation_id: string
  latency_ms: number
}

export async function getDocuments(): Promise<DocumentItem[]> {
  const { data } = await api.get<DocumentItem[]>('/documents')
  return data
}

export async function getDocument(documentId: string): Promise<DocumentItem> {
  const { data } = await api.get<DocumentItem>(`/documents/${documentId}`)
  return data
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData()
  formData.append('file', file)

  const { data } = await api.post<DocumentItem>('/documents', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return data
}

export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/documents/${documentId}`)
}

export async function askQuestion(payload: {
  document_id: string
  question: string
  conversation_id?: string | null
}): Promise<AskResponse> {
  const { data } = await api.post<AskResponse>('/ask', payload)
  return data
}

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0 && typeof detail[0]?.msg === 'string') {
      return detail[0].msg
    }
    if (error.message) {
      return error.message
    }
  }

  return 'The request could not be completed.'
}

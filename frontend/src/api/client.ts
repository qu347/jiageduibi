import type {
  AutomationEnvironment,
  CollectionRegionTaskView,
  CollectionRunView,
} from '../types/offers'


export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(message)
  }

  static async fromResponse(response: Response): Promise<ApiError> {
    let detail: unknown = null
    try {
      detail = await response.json()
    } catch {
      detail = await response.text()
    }
    return new ApiError(`请求失败（${response.status}）`, response.status, detail)
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw await ApiError.fromResponse(response)
  return response.json() as Promise<T>
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) throw await ApiError.fromResponse(response)
  return response.json() as Promise<T>
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await ApiError.fromResponse(response)
  return response.json() as Promise<T>
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': file.type,
      'X-File-Name': encodeURIComponent(file.name),
    },
    body: file,
  })
  if (!response.ok) throw await ApiError.fromResponse(response)
  return response.json() as Promise<T>
}


export const automaticCollectionApi = {
  environment: () => apiGet<AutomationEnvironment>('/api/automation/environment'),
  create: (sessionId: number) => apiPost<CollectionRunView>(
    `/api/search-sessions/${sessionId}/collection-runs`,
    { platform: 'jd' },
  ),
  get: (runId: number) => apiGet<CollectionRunView>(`/api/collection-runs/${runId}`),
  tasks: (runId: number) => apiGet<CollectionRegionTaskView[]>(`/api/collection-runs/${runId}/tasks`),
  pause: (runId: number) => apiPost<CollectionRunView>(`/api/collection-runs/${runId}/pause`, {}),
  resume: (runId: number) => apiPost<CollectionRunView>(`/api/collection-runs/${runId}/resume`, {}),
  stop: (runId: number) => apiPost<CollectionRunView>(`/api/collection-runs/${runId}/stop`, {}),
  retryFailed: (runId: number) => apiPost<CollectionRunView>(
    `/api/collection-runs/${runId}/retry-failed`,
    {},
  ),
}

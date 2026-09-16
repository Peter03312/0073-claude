import type {
  Card,
  CompareResponse,
  ProofDraft,
  ProofPayload,
  Track,
  VerifyResult,
  VersionInfo,
} from "./types";

/** API 错误：保留状态码与响应体（409 时 body 里有 current_revision）。 */
export class ApiError extends Error {
  constructor(
    public status: number,
    public body: { detail?: string; current_revision?: number } | null,
  ) {
    super(body?.detail ?? `HTTP ${status}`);
  }
}

async function request<T>(
  method: string,
  url: string,
  body?: unknown,
): Promise<T> {
  const resp = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    let data: ApiError["body"] = null;
    try {
      data = await resp.json();
    } catch {
      /* 非 JSON 错误体 */
    }
    throw new ApiError(resp.status, data);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  listProofs: () => request<ProofDraft[]>("GET", "/api/proofs"),

  createProof: (payload: ProofPayload & { title?: string }) =>
    request<ProofDraft>("POST", "/api/proofs", payload),

  getProof: (id: string) => request<ProofDraft>("GET", `/api/proofs/${id}`),

  updateProof: (
    id: string,
    revision: number,
    payload: { title: string; tracks: Track[]; cards: Card[] },
  ) =>
    request<ProofDraft>("PUT", `/api/proofs/${id}`, { ...payload, revision }),

  deleteProof: (id: string) => request<void>("DELETE", `/api/proofs/${id}`),

  /** 核验草稿；可携带尚未保存的内容。revision 不符会被 409 拒绝。 */
  verifyDraft: (id: string, revision: number, content?: ProofPayload) =>
    request<{ revision: number; result: VerifyResult }>(
      "POST",
      `/api/proofs/${id}/verify`,
      content ? { revision, ...content } : { revision },
    ),

  publishVersion: (id: string, revision: number, note?: string) =>
    request<VersionInfo>("POST", `/api/proofs/${id}/versions`, {
      revision,
      note: note ?? null,
    }),

  listVersions: (id: string) =>
    request<VersionInfo[]>("GET", `/api/proofs/${id}/versions`),

  getVersion: (id: string, no: number) =>
    request<VersionInfo>("GET", `/api/proofs/${id}/versions/${no}`),

  verifyVersion: (id: string, no: number) =>
    request<{ version_no: number; result: VerifyResult }>(
      "POST",
      `/api/proofs/${id}/versions/${no}/verify`,
    ),

  compare: (left: ProofPayload, right: ProofPayload) =>
    request<CompareResponse>("POST", "/api/compare", { left, right }),
};

/** 与后端约定的线格式：大整数一律用十进制字符串，绝不经 float64。 */

export type CardType = "source" | "combine" | "normalize" | "contradiction";

export interface Track {
  id: string;
  period: string;
  phase: string;
}

export interface Witness {
  u: string;
  v: string;
}

export type Card =
  | { type: "source"; track: string }
  | { type: "combine"; left: number; right: number; witness: Witness }
  | { type: "normalize"; card: number }
  | { type: "contradiction"; left: number; right: number };

export interface Judgment {
  kind: "congruence" | "contradiction";
  sources: string[];
  residue?: string;
  modulus?: string;
  canonical_residue?: string;
}

export interface StepResult {
  index: number;
  type: string;
  ok: boolean;
  code?: string;
  message?: string;
  judgment?: Judgment;
}

export interface FirstError {
  card_index: number | null;
  code: string;
  message: string;
}

export interface FinalJudgment extends Judgment {
  covers_all_tracks?: boolean;
}

export type VerifyStatus =
  | "solvable"
  | "unsolvable"
  | "incomplete"
  | "invalid"
  | "empty";

export interface VerifyResult {
  status: VerifyStatus;
  tracks_total: number;
  steps: StepResult[];
  first_error: FirstError | null;
  final: FinalJudgment | null;
}

export interface ProofDraft {
  id: string;
  title: string;
  revision: number;
  tracks: Track[];
  cards: Card[];
  created_at: string;
  updated_at: string;
  version_count: number;
}

export interface VersionInfo {
  proof_id: string;
  version_no: number;
  title: string;
  revision: number;
  tracks: Track[];
  cards: Card[];
  note: string | null;
  created_at: string;
}

export interface Comparison {
  kind: string;
  consistent?: boolean;
  equal?: boolean;
  gcd?: string;
  agree?: boolean;
  message: string;
}

export interface CompareResponse {
  left: VerifyResult;
  right: VerifyResult;
  comparison: Comparison;
}

export interface ProofPayload {
  tracks: Track[];
  cards: Card[];
}

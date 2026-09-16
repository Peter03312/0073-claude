"""证明卡核验器：任意精度整数、逐卡核验、定位首个错误。

数学背景（翻页动画的对齐问题）：
    每条轨道是一个周期循环，要求某一帧 x 满足
        x ≡ phase (mod period)
    整个问题是一组同余方程；合并两条同余式用中国剩余定理（CRT）：
        x ≡ a₁ (mod m₁),  x ≡ a₂ (mod m₂)
    有解当且仅当 a₁ ≡ a₂ (mod g)，其中 g = gcd(m₁, m₂)。
    给定 Bézout 见证 u·m₁ + v·m₂ = g，解为
        x ≡ a₁ + m₁·u·(a₂ − a₁)/g   (mod lcm(m₁, m₂))
    核验只做 O(位数) 的整数运算：gcd、乘法、整除，
    绝不枚举 0..lcm 的帧，也绝不使用浮点数。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd
from typing import Optional

from .models import (
    Card,
    CombineCard,
    ContradictionCard,
    NormalizeCard,
    ProofPayload,
    SourceCard,
    Track,
)

# ---------------------------------------------------------------------------
# 判断（judgment）：每张合法的卡推出一个结论
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Judgment:
    """congruence: x ≡ residue (mod modulus)，sources 为它依赖的轨道集合。

    contradiction: 来源子集内部冲突（无公共帧）。
    residue 按卡的构造原样保留（可能为负或超过模数），
    canonical_residue 才是最小非负剩余。
    """

    kind: str  # "congruence" | "contradiction"
    residue: Optional[int] = None
    modulus: Optional[int] = None
    sources: frozenset = field(default_factory=frozenset)

    @property
    def canonical_residue(self) -> Optional[int]:
        if self.kind != "congruence" or self.residue is None or self.modulus is None:
            return None
        return self.residue % self.modulus

    def to_wire(self) -> dict:
        out = {"kind": self.kind, "sources": sorted(self.sources)}
        if self.kind == "congruence":
            out["residue"] = str(self.residue)
            out["modulus"] = str(self.modulus)
            out["canonical_residue"] = str(self.canonical_residue)
        return out


@dataclass
class Step:
    index: int
    card_type: str
    ok: bool
    code: Optional[str] = None
    message: Optional[str] = None
    judgment: Optional[Judgment] = None

    def to_wire(self) -> dict:
        out = {"index": self.index, "type": self.card_type, "ok": self.ok}
        if self.code:
            out["code"] = self.code
        if self.message:
            out["message"] = self.message
        if self.judgment is not None:
            out["judgment"] = self.judgment.to_wire()
        return out


@dataclass
class VerifyResult:
    """status:
        solvable   —— 末卡为覆盖全部轨道的同余式，给出首次同帧帧号与循环周期
        unsolvable —— 末卡为冲突卡，其来源即一个不相容子集
        incomplete —— 每步都合法，但末卡同余式未覆盖全部轨道
        invalid    —— 某张卡非法（first_error 定位第一张非法卡）
        empty      —— 没有任何证明卡
    """

    status: str
    tracks_total: int
    steps: list = field(default_factory=list)  # list[Step]
    first_error: Optional[dict] = None
    final: Optional[dict] = None

    def to_wire(self) -> dict:
        return {
            "status": self.status,
            "tracks_total": self.tracks_total,
            "steps": [s.to_wire() for s in self.steps],
            "first_error": self.first_error,
            "final": self.final,
        }


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _fail(steps: list, index: Optional[int], code: str, message: str) -> VerifyResult:
    first_error = {"card_index": index, "code": code, "message": message}
    return VerifyResult(status="invalid", tracks_total=0, steps=steps, first_error=first_error)


def _check_ref(ref: int, current: int, role: str) -> Optional[str]:
    """引用必须指向严格位于当前卡之前的卡。"""
    if ref >= current:
        return f"{role} 引用了第 {ref} 张卡，但它不在本卡之前（只能引用更早的卡）"
    return None


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def verify_proof(payload: ProofPayload) -> VerifyResult:
    tracks = payload.tracks
    cards = payload.cards

    # ---- 轨道定义的合法性（证明级错误，不属于任何卡） ----
    track_map: dict[str, Track] = {}
    for t in tracks:
        if t.id in track_map:
            return _fail([], None, "DUPLICATE_TRACK", f"轨道 “{t.id}” 被重复定义")
        if t.period <= 0:
            return _fail([], None, "NON_POSITIVE_PERIOD", f"轨道 “{t.id}” 的周期必须为正整数")
        if t.phase < 0:
            return _fail([], None, "NEGATIVE_PHASE", f"轨道 “{t.id}” 的相位必须是非负整数（零基）")
        track_map[t.id] = t

    steps: list[Step] = []
    judgments: list[Judgment] = []

    for i, card in enumerate(cards):
        step, judgment = _verify_card(i, card, judgments, track_map)
        steps.append(step)
        if judgment is None:
            # 首个非法步骤：立即停止并定位
            result = _fail(steps, i, step.code or "INVALID", step.message or "非法证明卡")
            result.tracks_total = len(tracks)
            return result
        judgments.append(judgment)

    if not cards:
        return VerifyResult(status="empty", tracks_total=len(tracks), steps=steps)

    final = judgments[-1]
    all_tracks = frozenset(track_map)
    if final.kind == "contradiction":
        # 无解：任一不相容子集都足以证明
        final_wire = {"kind": "contradiction", "sources": sorted(final.sources)}
        return VerifyResult(
            status="unsolvable",
            tracks_total=len(tracks),
            steps=steps,
            final=final_wire,
        )
    covers_all = final.sources == all_tracks
    final_wire = final.to_wire()
    final_wire["covers_all_tracks"] = covers_all
    return VerifyResult(
        status="solvable" if covers_all else "incomplete",
        tracks_total=len(tracks),
        steps=steps,
        final=final_wire,
    )


def _verify_card(
    index: int,
    card: Card,
    judgments: list[Judgment],
    track_map: dict[str, Track],
) -> tuple[Step, Optional[Judgment]]:
    if isinstance(card, SourceCard):
        return _verify_source(index, card, track_map)
    if isinstance(card, CombineCard):
        return _verify_combine(index, card, judgments)
    if isinstance(card, NormalizeCard):
        return _verify_normalize(index, card, judgments)
    if isinstance(card, ContradictionCard):
        return _verify_contradiction(index, card, judgments)
    return Step(index, "unknown", False, "BAD_CARD_TYPE", "未知的证明卡类型"), None


def _verify_source(
    index: int, card: SourceCard, track_map: dict[str, Track]
) -> tuple[Step, Optional[Judgment]]:
    track = track_map.get(card.track)
    if track is None:
        return (
            Step(index, "source", False, "UNKNOWN_TRACK", f"轨道 “{card.track}” 未在 tracks 中定义"),
            None,
        )
    judgment = Judgment(
        kind="congruence",
        residue=track.phase,
        modulus=track.period,
        sources=frozenset({track.id}),
    )
    return Step(index, "source", True, judgment=judgment), judgment


def _verify_combine(
    index: int, card: CombineCard, judgments: list[Judgment]
) -> tuple[Step, Optional[Judgment]]:
    for role, ref in (("left", card.left), ("right", card.right)):
        err = _check_ref(ref, index, role)
        if err:
            return Step(index, "combine", False, "BAD_REFERENCE", err), None
    left = judgments[card.left]
    right = judgments[card.right]
    for role, j in (("左", left), ("右", right)):
        if j.kind != "congruence":
            return (
                Step(index, "combine", False, "NOT_CONGRUENCE", f"{role}卡是冲突结论，不能参与合并"),
                None,
            )
    overlap = left.sources & right.sources
    if overlap:
        return (
            Step(
                index,
                "combine",
                False,
                "OVERLAPPING_SOURCES",
                "合并要求来源不相交，但共同依赖了轨道：" + "、".join(sorted(overlap)),
            ),
            None,
        )
    a1, m1 = left.residue, left.modulus
    a2, m2 = right.residue, right.modulus
    u, v = card.witness.u, card.witness.v
    g = gcd(m1, m2)
    bezout = u * m1 + v * m2
    if bezout != g:
        return (
            Step(
                index,
                "combine",
                False,
                "BAD_WITNESS",
                f"Bézout 见证不成立：u·m₁+v·m₂ = {bezout}，但 gcd(m₁, m₂) = {g}",
            ),
            None,
        )
    diff = a2 - a1
    if diff % g != 0:
        return (
            Step(
                index,
                "combine",
                False,
                "INCOMPATIBLE",
                f"相位差 {diff} 不能被 gcd = {g} 整除，两卡不相容（应使用 contradiction 卡）",
            ),
            None,
        )
    k = diff // g  # 整除，精确
    residue = a1 + m1 * u * k
    modulus = (m1 // g) * m2  # lcm(m₁, m₂)，精确
    judgment = Judgment(
        kind="congruence",
        residue=residue,
        modulus=modulus,
        sources=left.sources | right.sources,
    )
    return Step(index, "combine", True, judgment=judgment), judgment


def _verify_normalize(
    index: int, card: NormalizeCard, judgments: list[Judgment]
) -> tuple[Step, Optional[Judgment]]:
    err = _check_ref(card.card, index, "card")
    if err:
        return Step(index, "normalize", False, "BAD_REFERENCE", err), None
    prev = judgments[card.card]
    if prev.kind != "congruence":
        return (
            Step(index, "normalize", False, "NOT_CONGRUENCE", "被规范化的卡是冲突结论，没有余数可化简"),
            None,
        )
    judgment = Judgment(
        kind="congruence",
        residue=prev.residue % prev.modulus,  # 最小非负剩余
        modulus=prev.modulus,
        sources=prev.sources,
    )
    return Step(index, "normalize", True, judgment=judgment), judgment


def _verify_contradiction(
    index: int, card: ContradictionCard, judgments: list[Judgment]
) -> tuple[Step, Optional[Judgment]]:
    for role, ref in (("left", card.left), ("right", card.right)):
        err = _check_ref(ref, index, role)
        if err:
            return Step(index, "contradiction", False, "BAD_REFERENCE", err), None
    left = judgments[card.left]
    right = judgments[card.right]
    for role, j in (("左", left), ("右", right)):
        if j.kind != "congruence":
            return (
                Step(index, "contradiction", False, "NOT_CONGRUENCE", f"{role}卡已经是冲突结论，不能再次取冲突"),
                None,
            )
    g = gcd(left.modulus, right.modulus)
    diff = right.residue - left.residue
    if diff % g == 0:
        return (
            Step(
                index,
                "contradiction",
                False,
                "COMPATIBLE",
                f"相位差 {diff} 能被 gcd = {g} 整除，两卡其实相容，不能声明冲突",
            ),
            None,
        )
    judgment = Judgment(kind="contradiction", sources=left.sources | right.sources)
    return Step(index, "contradiction", True, judgment=judgment), judgment


# ---------------------------------------------------------------------------
# 对照两份证明：规范余数 + 模最小公倍数
# ---------------------------------------------------------------------------


def compare_results(left: VerifyResult, right: VerifyResult) -> dict:
    """比较两份已核验证明的最终结论。

    两份可解证明若覆盖同一轨道全集，则模数都是全部周期的最小公倍数，
    此时“规范余数相等”当且仅当两种合并顺序给出同一个对齐帧。
    """
    lf, rf = left.final, right.final
    if left.status == "invalid" or right.status == "invalid":
        return {"kind": "invalid", "message": "至少一份证明存在非法步骤，无法对照"}
    if lf is None or rf is None:
        return {"kind": "invalid", "message": "至少一份证明没有最终结论，无法对照"}

    if lf["kind"] == "congruence" and rf["kind"] == "congruence":
        a_l, m_l = int(lf["canonical_residue"]), int(lf["modulus"])
        a_r, m_r = int(rf["canonical_residue"]), int(rf["modulus"])
        g = gcd(m_l, m_r)
        consistent = (a_l - a_r) % g == 0
        equal = m_l == m_r and a_l == a_r
        if equal:
            message = f"两种合并顺序结论一致：第 {a_l} 帧首次同帧，每 {m_l} 帧循环一次"
        elif consistent:
            message = (
                f"两份结论相容但不完全相同（覆盖范围可能不同）："
                f"左 x≡{a_l} (mod {m_l})，右 x≡{a_r} (mod {m_r})，gcd = {g}"
            )
        else:
            message = (
                f"两份结论互相矛盾：左 x≡{a_l} (mod {m_l})，右 x≡{a_r} (mod {m_r})，"
                f"差值不能被 gcd = {g} 整除"
            )
        return {
            "kind": "congruences",
            "consistent": consistent,
            "equal": equal,
            "gcd": str(g),
            "message": message,
        }

    if lf["kind"] == "contradiction" and rf["kind"] == "contradiction":
        return {
            "kind": "both_unsolvable",
            "agree": True,
            "message": "两份证明都判定无解（各自给出了不相容子集）",
        }
    return {
        "kind": "mixed",
        "agree": False,
        "message": "一份证明可解、另一份证明无解，结论相反",
    }

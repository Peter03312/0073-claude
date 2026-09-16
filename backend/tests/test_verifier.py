"""核验器单元测试：兼容 / 冲突 / 坏见证 / 非法依赖 / 大整数 / 规范化 / 覆盖判定。

所有期望都通过独立方法现算（扩展欧几里得、暴力枚举小周期），
不与被测实现共享代码，也不硬编码答案。
"""
from __future__ import annotations

import random
from math import gcd, lcm

import pytest

from app.models import (
    CombineCard,
    ContradictionCard,
    NormalizeCard,
    ProofPayload,
    SourceCard,
    Track,
    Witness,
)
from app.verifier import compare_results, verify_proof


# ---------------------------------------------------------------------------
# 独立工具：与被测实现无关
# ---------------------------------------------------------------------------


def egcd(a: int, b: int) -> tuple[int, int, int]:
    """返回 (g, u, v) 使 u·a + v·b = g = gcd(a, b)，g ≥ 0。"""
    if b == 0:
        return (a, 1, 0)
    g, u1, v1 = egcd(b, a % b)
    return (g, v1, u1 - (a // b) * v1)


def brute_solutions(tracks: list[Track], limit: int) -> list[int]:
    """小范围内暴力枚举所有同帧帧号（仅测试用，核验器本身禁止这么做）。"""
    return [
        x
        for x in range(limit)
        if all(x % t.period == t.phase % t.period for t in tracks)
    ]


def make_tracks(spec: list[tuple[str, int, int]]) -> list[Track]:
    return [Track(id=i, period=p, phase=ph) for i, p, ph in spec]


def build_chain(tracks: list[Track], order: list[int]) -> ProofPayload:
    """按给定顺序左折叠合并全部轨道（仅用于必然相容的系统）。"""
    cards: list = [SourceCard(track=t.id) for t in tracks]
    acc_idx = order[0]
    acc_a, acc_m = tracks[order[0]].phase, tracks[order[0]].period
    for k in order[1:]:
        t = tracks[k]
        g, u, v = egcd(acc_m, t.period)
        assert (t.phase - acc_a) % g == 0, "测试前提：系统必须相容"
        cards.append(CombineCard(left=acc_idx, right=k, witness=Witness(u=u, v=v)))
        acc_idx = len(cards) - 1
        acc_a = acc_a + acc_m * u * ((t.phase - acc_a) // g)
        acc_m = acc_m // g * t.period
    cards.append(NormalizeCard(card=acc_idx))
    return ProofPayload(tracks=tracks, cards=cards)


def find_incompatible_pair(tracks: list[Track]) -> tuple[int, int]:
    for i in range(len(tracks)):
        for j in range(i + 1, len(tracks)):
            g = gcd(tracks[i].period, tracks[j].period)
            if (tracks[i].phase - tracks[j].phase) % g != 0:
                return i, j
    raise AssertionError("系统是相容的，找不到冲突对")


# ---------------------------------------------------------------------------
# 兼容：合并得到正确的同余式
# ---------------------------------------------------------------------------


def test_compatible_pair_matches_bruteforce():
    tracks = make_tracks([("a", 4, 1), ("b", 6, 3)])
    payload = build_chain(tracks, [0, 1])
    result = verify_proof(payload)
    assert result.status == "solvable"
    final = result.final
    assert final["covers_all_tracks"] is True
    r, m = int(final["canonical_residue"]), int(final["modulus"])
    assert m == lcm(4, 6)
    expected = brute_solutions(tracks, m)
    assert expected and all(x % m == r for x in expected)


def test_random_systems_match_bruteforce():
    rng = random.Random(20260915)
    for _ in range(300):
        n = rng.randint(2, 5)
        tracks = make_tracks(
            [(f"t{k}", rng.randint(1, 12), rng.randint(0, 15)) for k in range(n)]
        )
        total_lcm = lcm(*[t.period for t in tracks])
        sols = brute_solutions(tracks, total_lcm)
        if sols:
            payload = build_chain(tracks, list(range(n)))
            result = verify_proof(payload)
            assert result.status == "solvable", result.first_error
            r = int(result.final["canonical_residue"])
            m = int(result.final["modulus"])
            assert m == total_lcm
            assert all(x % m == r % m for x in sols)
        else:
            i, j = find_incompatible_pair(tracks)
            payload = ProofPayload(
                tracks=tracks,
                cards=[
                    SourceCard(track=tracks[i].id),
                    SourceCard(track=tracks[j].id),
                    ContradictionCard(left=0, right=1),
                ],
            )
            result = verify_proof(payload)
            assert result.status == "unsolvable"
            assert set(result.final["sources"]) == {tracks[i].id, tracks[j].id}


def test_merge_orders_agree_via_compare():
    """同一组轨道、三种不同合并顺序，规范余数与模最小公倍数必须一致。"""
    rng = random.Random(7)
    for _ in range(50):
        n = rng.randint(3, 6)
        # 构造必然相容的系统：先定答案再反推相位
        periods = [rng.randint(1, 9) for _ in range(n)]
        total_lcm = lcm(*periods)
        answer = rng.randrange(total_lcm)
        tracks = make_tracks(
            [(f"t{k}", periods[k], answer % periods[k]) for k in range(n)]
        )
        orders = [list(range(n)), list(reversed(range(n))), rng.sample(range(n), n)]
        results = [verify_proof(build_chain(tracks, o)) for o in orders]
        assert all(r.status == "solvable" for r in results)
        for r in results[1:]:
            cmp = compare_results(results[0], r)
            assert cmp["consistent"] is True
            assert cmp["equal"] is True
            assert int(results[0].final["modulus"]) == total_lcm
            assert int(r.final["canonical_residue"]) == answer % total_lcm


# ---------------------------------------------------------------------------
# 冲突：contradiction 卡合法；对不相容卡 combine 必须被拒
# ---------------------------------------------------------------------------


def test_contradiction_accepted_when_phases_clash():
    tracks = make_tracks([("a", 4, 0), ("b", 6, 1)])
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            ContradictionCard(left=0, right=1),
        ],
    )
    result = verify_proof(payload)
    assert result.status == "unsolvable"
    assert result.final["kind"] == "contradiction"
    assert set(result.final["sources"]) == {"a", "b"}


def test_contradiction_rejected_when_compatible():
    tracks = make_tracks([("a", 4, 1), ("b", 6, 3)])
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            ContradictionCard(left=0, right=1),
        ],
    )
    result = verify_proof(payload)
    assert result.status == "invalid"
    assert result.first_error["card_index"] == 2
    assert result.first_error["code"] == "COMPATIBLE"


def test_combine_rejected_when_incompatible():
    tracks = make_tracks([("a", 4, 0), ("b", 6, 1)])
    g, u, v = egcd(4, 6)
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            CombineCard(left=0, right=1, witness=Witness(u=u, v=v)),
        ],
    )
    result = verify_proof(payload)
    assert result.status == "invalid"
    assert result.first_error["card_index"] == 2
    assert result.first_error["code"] == "INCOMPATIBLE"


def test_unsolvable_proof_may_use_any_incompatible_subset():
    """三条轨道里只有两条冲突：用该子集即可证明无解，无需覆盖全部轨道。"""
    tracks = make_tracks([("a", 5, 1), ("b", 4, 0), ("c", 6, 1)])
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="b"),
            SourceCard(track="c"),
            ContradictionCard(left=0, right=1),
        ],
    )
    result = verify_proof(payload)
    assert result.status == "unsolvable"
    assert set(result.final["sources"]) == {"b", "c"}


# ---------------------------------------------------------------------------
# 坏见证：Bézout 等式必须精确成立
# ---------------------------------------------------------------------------


def test_bad_witness_rejected():
    tracks = make_tracks([("a", 4, 1), ("b", 6, 3)])
    g, u, v = egcd(4, 6)
    for bad_u, bad_v in [(u + 1, v), (u, v - 1), (0, 0), (v, u)]:
        if bad_u * 4 + bad_v * 6 == g:
            continue  # 恰好也是合法见证则跳过
        payload = ProofPayload(
            tracks=tracks,
            cards=[
                SourceCard(track="a"),
                SourceCard(track="b"),
                CombineCard(left=0, right=1, witness=Witness(u=bad_u, v=bad_v)),
            ],
        )
        result = verify_proof(payload)
        assert result.status == "invalid"
        assert result.first_error["card_index"] == 2
        assert result.first_error["code"] == "BAD_WITNESS"


def test_witness_must_match_actual_gcd():
    """m₁、m₂ 不互素时，拿 1 当 gcd 的见证不合法。"""
    tracks = make_tracks([("a", 6, 0), ("b", 9, 3)])
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            CombineCard(left=0, right=1, witness=Witness(u=-1, v=1)),  # -6+9=3=g ✓ 其实合法
        ],
    )
    assert verify_proof(payload).status == "solvable"
    payload_bad = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            CombineCard(left=0, right=1, witness=Witness(u=2, v=-1)),  # 12-9=3 ✓ 也合法？
        ],
    )
    # 2·6 + (−1)·9 = 3 = g，确实合法 —— 换一个真正不成立的
    assert verify_proof(payload_bad).status == "solvable"
    payload_wrong = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            CombineCard(left=0, right=1, witness=Witness(u=1, v=0)),  # 6 ≠ 3
        ],
    )
    result = verify_proof(payload_wrong)
    assert result.status == "invalid"
    assert result.first_error["code"] == "BAD_WITNESS"


# ---------------------------------------------------------------------------
# 非法依赖：引用未来/自身/越界/类型不符/来源相交
# ---------------------------------------------------------------------------


def test_reference_to_future_card_rejected():
    tracks = make_tracks([("a", 4, 1), ("b", 6, 3)])
    g, u, v = egcd(4, 6)
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            CombineCard(left=1, right=2, witness=Witness(u=u, v=v)),  # 引用了未来的卡
            SourceCard(track="a"),
            SourceCard(track="b"),
        ],
    )
    result = verify_proof(payload)
    assert result.status == "invalid"
    assert result.first_error["card_index"] == 0
    assert result.first_error["code"] == "BAD_REFERENCE"


def test_self_reference_rejected():
    tracks = make_tracks([("a", 4, 1)])
    payload = ProofPayload(
        tracks=tracks,
        cards=[SourceCard(track="a"), NormalizeCard(card=1)],  # 引用自己
    )
    result = verify_proof(payload)
    assert result.status == "invalid"
    assert result.first_error["card_index"] == 1
    assert result.first_error["code"] == "BAD_REFERENCE"


def test_combine_with_contradiction_card_rejected():
    tracks = make_tracks([("a", 4, 0), ("b", 6, 1), ("c", 5, 2)])
    g, u, v = egcd(4, 5)
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            ContradictionCard(left=0, right=1),
            SourceCard(track="c"),
            CombineCard(left=2, right=3, witness=Witness(u=u, v=v)),  # 左卡是冲突结论
        ],
    )
    result = verify_proof(payload)
    assert result.status == "invalid"
    assert result.first_error["card_index"] == 4
    assert result.first_error["code"] == "NOT_CONGRUENCE"


def test_normalize_contradiction_rejected():
    tracks = make_tracks([("a", 4, 0), ("b", 6, 1)])
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            ContradictionCard(left=0, right=1),
            NormalizeCard(card=2),
        ],
    )
    result = verify_proof(payload)
    assert result.status == "invalid"
    assert result.first_error["card_index"] == 3
    assert result.first_error["code"] == "NOT_CONGRUENCE"


def test_overlapping_sources_rejected():
    tracks = make_tracks([("a", 4, 1), ("b", 6, 3)])
    g, u, v = egcd(4, 6)
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            CombineCard(left=0, right=1, witness=Witness(u=u, v=v)),
            CombineCard(left=2, right=0, witness=Witness(u=0, v=1)),  # {a,b} 与 {a} 相交
        ],
    )
    result = verify_proof(payload)
    assert result.status == "invalid"
    assert result.first_error["card_index"] == 3
    assert result.first_error["code"] == "OVERLAPPING_SOURCES"


def test_unknown_track_rejected():
    payload = ProofPayload(
        tracks=make_tracks([("a", 4, 1)]),
        cards=[SourceCard(track="ghost")],
    )
    result = verify_proof(payload)
    assert result.status == "invalid"
    assert result.first_error["card_index"] == 0
    assert result.first_error["code"] == "UNKNOWN_TRACK"


def test_track_level_errors():
    dup = ProofPayload(
        tracks=make_tracks([("a", 4, 1), ("a", 5, 1)]), cards=[]
    )
    assert verify_proof(dup).first_error["code"] == "DUPLICATE_TRACK"
    zero = ProofPayload(tracks=make_tracks([("a", 0, 1)]), cards=[])
    assert verify_proof(zero).first_error["code"] == "NON_POSITIVE_PERIOD"
    neg = ProofPayload(tracks=make_tracks([("a", 4, -1)]), cards=[])
    assert verify_proof(neg).first_error["code"] == "NEGATIVE_PHASE"


# ---------------------------------------------------------------------------
# normalize：只化为最小非负剩余
# ---------------------------------------------------------------------------


def test_normalize_reduces_to_least_residue():
    tracks = make_tracks([("a", 4, 1), ("b", 6, 3)])
    g, u, v = egcd(4, 6)
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            CombineCard(left=0, right=1, witness=Witness(u=u, v=v)),
            NormalizeCard(card=2),
        ],
    )
    result = verify_proof(payload)
    assert result.status == "solvable"
    combine_step = result.steps[2]
    raw = int(combine_step.judgment.residue)
    assert raw != raw % 12 or raw < 0 or raw >= 12  # 合并余数未规范化
    norm_step = result.steps[3]
    assert int(norm_step.judgment.residue) == raw % 12
    assert norm_step.judgment.modulus == combine_step.judgment.modulus
    assert result.final["canonical_residue"] == str(raw % 12)


def test_incomplete_cover():
    """末卡同余式没有覆盖全部轨道 → incomplete。"""
    tracks = make_tracks([("a", 4, 1), ("b", 6, 3), ("c", 5, 2)])
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="a"),
            SourceCard(track="b"),
            *build_chain(tracks[:2], [0, 1]).cards[2:],
        ],
    )
    result = verify_proof(payload)
    assert result.status == "incomplete"
    assert result.final["covers_all_tracks"] is False


def test_empty_proof():
    result = verify_proof(ProofPayload(tracks=make_tracks([("a", 4, 1)]), cards=[]))
    assert result.status == "empty"


# ---------------------------------------------------------------------------
# 大整数：任意精度，浮点实现必然出错的地方
# ---------------------------------------------------------------------------


def test_bigint_beyond_float64_precision():
    """m₁ = 2⁵⁴+1 与 m₂ = 2⁵⁴+2 互素；float64 会把二者舍成同一个数 2⁵⁴，
    浮点实现会算出 gcd = 2⁵⁴、相位差 1 不整除，从而误判不相容。
    任意精度下必须判相容。"""
    m1 = 2**54 + 1
    m2 = m1 + 1
    assert float(m1) == float(m2)  # 确认浮点确实区分不了
    g, u, v = egcd(m1, m2)
    assert g == 1
    tracks = make_tracks([("p", m1, 0), ("q", m2, 1)])
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="p"),
            SourceCard(track="q"),
            CombineCard(left=0, right=1, witness=Witness(u=u, v=v)),
        ],
    )
    result = verify_proof(payload)
    assert result.status == "solvable"
    r = int(result.final["canonical_residue"])
    m = int(result.final["modulus"])
    assert m == m1 * m2
    assert r % m1 == 0 and r % m2 == 1


def test_huge_bigint_via_decimal_strings():
    """40 位十进制字符串直接作为输入；结果用独立同余检验核对。"""
    n = 10**40
    m1, m2 = n + 1, n + 3  # 均为奇数且相差 2 → 互素
    a1 = 1234567890123456789012345678901234567890
    a2 = 987654321098765432109876543210987654321
    g, u, v = egcd(m1, m2)
    assert g == 1
    tracks = [
        Track(id="p", period=str(m1), phase=str(a1)),
        Track(id="q", period=str(m2), phase=str(a2)),
    ]
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="p"),
            SourceCard(track="q"),
            CombineCard(left=0, right=1, witness=Witness(u=str(u), v=str(v))),
            NormalizeCard(card=2),
        ],
    )
    result = verify_proof(payload)
    assert result.status == "solvable"
    r = int(result.final["canonical_residue"])
    m = int(result.final["modulus"])
    assert m == m1 * m2
    assert r % m1 == a1 % m1
    assert r % m2 == a2 % m2


def test_bigint_contradiction_exact():
    """模数相同、相位差 1：任意精度下 g = m，差 1 不整除 → 冲突。"""
    m = 10**30
    tracks = make_tracks([("p", m, 0), ("q", m, 1)])
    payload = ProofPayload(
        tracks=tracks,
        cards=[
            SourceCard(track="p"),
            SourceCard(track="q"),
            ContradictionCard(left=0, right=1),
        ],
    )
    assert verify_proof(payload).status == "unsolvable"


def test_float_and_bool_inputs_rejected():
    from pydantic import ValidationError

    for bad in [1.5, 1e30, True, "abc", "1.5", ""]:
        with pytest.raises(ValidationError):
            Track(id="x", period=bad, phase=0)
    # 超大整数字符串也要拒绝（防御性上限）
    with pytest.raises(ValidationError):
        Track(id="x", period="9" * 20000, phase=0)

"""API 集成测试：草稿 revision 乐观锁、不可变版本、核验、对照、版本竞态。

每个测试用独立临时 SQLite 库；期望行为通过接口语义现算，不硬编码。
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import create_app  # noqa: E402


def egcd(a: int, b: int) -> tuple[int, int, int]:
    if b == 0:
        return (a, 1, 0)
    g, u1, v1 = egcd(b, a % b)
    return (g, v1, u1 - (a // b) * v1)


@pytest.fixture()
def client(tmp_path):
    app = create_app(str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def compatible_proof() -> dict:
    g, u, v = egcd(4, 6)
    assert g == 2
    return {
        "title": "兼容示例",
        "tracks": [
            {"id": "翅膀", "period": "4", "phase": "1"},
            {"id": "尾巴", "period": "6", "phase": "3"},
        ],
        "cards": [
            {"type": "source", "track": "翅膀"},
            {"type": "source", "track": "尾巴"},
            {"type": "combine", "left": 0, "right": 1, "witness": {"u": str(u), "v": str(v)}},
            {"type": "normalize", "card": 2},
        ],
    }


def conflict_proof() -> dict:
    return {
        "title": "冲突示例",
        "tracks": [
            {"id": "左手", "period": "4", "phase": "0"},
            {"id": "右手", "period": "6", "phase": "1"},
        ],
        "cards": [
            {"type": "source", "track": "左手"},
            {"type": "source", "track": "右手"},
            {"type": "contradiction", "left": 0, "right": 1},
        ],
    }


def create(client: TestClient, payload: dict) -> dict:
    resp = client.post("/api/proofs", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 草稿 revision 与乐观锁
# ---------------------------------------------------------------------------


def test_draft_revision_flow(client):
    proof = create(client, compatible_proof())
    assert proof["revision"] == 1

    ok = client.put(
        f"/api/proofs/{proof['id']}",
        json={**compatible_proof(), "title": "改名", "revision": 1},
    )
    assert ok.status_code == 200
    assert ok.json()["revision"] == 2
    assert ok.json()["title"] == "改名"

    stale = client.put(
        f"/api/proofs/{proof['id']}",
        json={**compatible_proof(), "revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["current_revision"] == 2

    fresh = client.put(
        f"/api/proofs/{proof['id']}",
        json={**compatible_proof(), "revision": 2},
    )
    assert fresh.status_code == 200
    assert fresh.json()["revision"] == 3


def test_concurrent_writers_last_one_rejected(client):
    """两个客户端都基于 revision 1 保存：先写者成功，迟到者 409。"""
    proof = create(client, compatible_proof())
    body = {**compatible_proof(), "revision": proof["revision"]}
    first = client.put(f"/api/proofs/{proof['id']}", json=body)
    second = client.put(f"/api/proofs/{proof['id']}", json=body)
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["current_revision"] == first.json()["revision"]


# ---------------------------------------------------------------------------
# 核验：revision 不符拒绝；可附带未保存内容
# ---------------------------------------------------------------------------


def test_verify_requires_current_revision(client):
    proof = create(client, compatible_proof())
    ok = client.post(f"/api/proofs/{proof['id']}/verify", json={"revision": 1})
    assert ok.status_code == 200
    assert ok.json()["result"]["status"] == "solvable"

    client.put(
        f"/api/proofs/{proof['id']}",
        json={**compatible_proof(), "revision": 1},
    )
    stale = client.post(f"/api/proofs/{proof['id']}/verify", json={"revision": 1})
    assert stale.status_code == 409
    fresh = client.post(f"/api/proofs/{proof['id']}/verify", json={"revision": 2})
    assert fresh.status_code == 200


def test_verify_with_inline_unsaved_content(client):
    proof = create(client, compatible_proof())
    inline = conflict_proof()
    resp = client.post(
        f"/api/proofs/{proof['id']}/verify",
        json={
            "revision": proof["revision"],
            "tracks": inline["tracks"],
            "cards": inline["cards"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "unsolvable"
    # 草稿内容未被改动
    assert client.get(f"/api/proofs/{proof['id']}").json()["tracks"] == proof["tracks"]
    # 只给一半内容 → 422
    half = client.post(
        f"/api/proofs/{proof['id']}/verify",
        json={"revision": proof["revision"], "tracks": inline["tracks"]},
    )
    assert half.status_code == 422


# ---------------------------------------------------------------------------
# 不可变版本与版本竞态
# ---------------------------------------------------------------------------


def test_versions_are_immutable_and_ordered(client):
    proof = create(client, compatible_proof())
    v1 = client.post(
        f"/api/proofs/{proof['id']}/versions",
        json={"revision": 1, "note": "第一版"},
    )
    assert v1.status_code == 201
    assert v1.json()["version_no"] == 1

    # 草稿继续前进
    client.put(
        f"/api/proofs/{proof['id']}",
        json={**conflict_proof(), "title": "改成冲突版", "revision": 1},
    )
    # 用旧 revision 发布 → 409（版本竞态）
    stale = client.post(
        f"/api/proofs/{proof['id']}/versions", json={"revision": 1}
    )
    assert stale.status_code == 409
    assert stale.json()["current_revision"] == 2

    v2 = client.post(
        f"/api/proofs/{proof['id']}/versions", json={"revision": 2}
    )
    assert v2.status_code == 201
    assert v2.json()["version_no"] == 2

    # v1 内容不受草稿后续修改影响
    got_v1 = client.get(f"/api/proofs/{proof['id']}/versions/1").json()
    assert got_v1["tracks"] == compatible_proof()["tracks"]
    assert got_v1["note"] == "第一版"
    got_v2 = client.get(f"/api/proofs/{proof['id']}/versions/2").json()
    assert got_v2["tracks"] == conflict_proof()["tracks"]

    versions = client.get(f"/api/proofs/{proof['id']}/versions").json()
    assert [v["version_no"] for v in versions] == [1, 2]

    # 版本不可变：没有修改入口
    assert client.put(
        f"/api/proofs/{proof['id']}/versions/1", json={}
    ).status_code == 405

    # 核验版本（内容固定，无需 revision）
    check = client.post(f"/api/proofs/{proof['id']}/versions/1/verify")
    assert check.status_code == 200
    assert check.json()["result"]["status"] == "solvable"
    check2 = client.post(f"/api/proofs/{proof['id']}/versions/2/verify")
    assert check2.json()["result"]["status"] == "unsolvable"


def test_publish_race_between_two_clients(client):
    """两个客户端同时基于 revision 1 发布：都会成功生成各自版本号，
    但随后基于旧 revision 的写入必须 409。"""
    proof = create(client, compatible_proof())
    a = client.post(f"/api/proofs/{proof['id']}/versions", json={"revision": 1})
    b = client.post(f"/api/proofs/{proof['id']}/versions", json={"revision": 1})
    assert a.status_code == 201 and b.status_code == 201
    assert {a.json()["version_no"], b.json()["version_no"]} == {1, 2}
    # 草稿 revision 未变（发布不修改草稿），但内容若被更新，旧 revision 立即失效
    client.put(
        f"/api/proofs/{proof['id']}",
        json={**compatible_proof(), "revision": 1},
    )
    late = client.post(f"/api/proofs/{proof['id']}/versions", json={"revision": 1})
    assert late.status_code == 409


# ---------------------------------------------------------------------------
# 对照：不同合并顺序 / 可解与无解
# ---------------------------------------------------------------------------


def test_compare_merge_orders(client):
    tracks = [
        {"id": "a", "period": "4", "phase": "1"},
        {"id": "b", "period": "6", "phase": "3"},
        {"id": "c", "period": "5", "phase": "2"},
    ]

    def chain(order: list[int]) -> list:
        cards = [{"type": "source", "track": t["id"]} for t in tracks]
        acc_idx = order[0]
        acc_a = int(tracks[order[0]]["phase"])
        acc_m = int(tracks[order[0]]["period"])
        for k in order[1:]:
            p, ph = int(tracks[k]["period"]), int(tracks[k]["phase"])
            g, u, v = egcd(acc_m, p)
            assert (ph - acc_a) % g == 0
            cards.append(
                {
                    "type": "combine",
                    "left": acc_idx,
                    "right": k,
                    "witness": {"u": str(u), "v": str(v)},
                }
            )
            acc_idx = len(cards) - 1
            acc_a = acc_a + acc_m * u * ((ph - acc_a) // g)
            acc_m = acc_m // g * p
        cards.append({"type": "normalize", "card": acc_idx})
        return cards

    resp = client.post(
        "/api/compare",
        json={
            "left": {"tracks": tracks, "cards": chain([0, 1, 2])},
            "right": {"tracks": tracks, "cards": chain([2, 1, 0])},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["left"]["status"] == "solvable"
    assert body["right"]["status"] == "solvable"
    cmp = body["comparison"]
    assert cmp["consistent"] is True
    assert cmp["equal"] is True

    mixed = client.post(
        "/api/compare",
        json={
            "left": {"tracks": tracks, "cards": chain([0, 1, 2])},
            "right": {"tracks": conflict_proof()["tracks"], "cards": conflict_proof()["cards"]},
        },
    ).json()
    assert mixed["comparison"]["kind"] == "mixed"

    both_bad = client.post(
        "/api/compare",
        json={
            "left": {"tracks": conflict_proof()["tracks"], "cards": conflict_proof()["cards"]},
            "right": {"tracks": conflict_proof()["tracks"], "cards": conflict_proof()["cards"]},
        },
    ).json()
    assert both_bad["comparison"]["kind"] == "both_unsolvable"


# ---------------------------------------------------------------------------
# 错误定位经 API 透出
# ---------------------------------------------------------------------------


def test_first_error_located_via_api(client):
    proof = dict(compatible_proof())
    proof["cards"] = [
        {"type": "source", "track": "翅膀"},
        {"type": "source", "track": "尾巴"},
        {"type": "combine", "left": 0, "right": 1, "witness": {"u": "1", "v": "1"}},
    ]
    created = create(client, proof)
    resp = client.post(
        f"/api/proofs/{created['id']}/verify", json={"revision": 1}
    )
    result = resp.json()["result"]
    assert result["status"] == "invalid"
    assert result["first_error"]["card_index"] == 2
    assert result["first_error"]["code"] == "BAD_WITNESS"
    # 错误步骤之后的卡不应出现
    assert len(result["steps"]) == 3


def test_illegal_dependency_via_api(client):
    proof = dict(compatible_proof())
    proof["cards"] = [
        {"type": "source", "track": "翅膀"},
        {"type": "normalize", "card": 3},  # 引用未来
    ]
    created = create(client, proof)
    result = client.post(
        f"/api/proofs/{created['id']}/verify", json={"revision": 1}
    ).json()["result"]
    assert result["first_error"]["code"] == "BAD_REFERENCE"
    assert result["first_error"]["card_index"] == 1


# ---------------------------------------------------------------------------
# 大整数与输入纪律
# ---------------------------------------------------------------------------


def test_bigint_strings_via_api(client):
    n = 10**40
    m1, m2 = n + 1, n + 3
    g, u, v = egcd(m1, m2)
    assert g == 1
    proof = {
        "title": "大整数",
        "tracks": [
            {"id": "p", "period": str(m1), "phase": "0"},
            {"id": "q", "period": str(m2), "phase": "1"},
        ],
        "cards": [
            {"type": "source", "track": "p"},
            {"type": "source", "track": "q"},
            {"type": "combine", "left": 0, "right": 1, "witness": {"u": str(u), "v": str(v)}},
        ],
    }
    created = create(client, proof)
    result = client.post(
        f"/api/proofs/{created['id']}/verify", json={"revision": 1}
    ).json()["result"]
    assert result["status"] == "solvable"
    r = int(result["final"]["canonical_residue"])
    m = int(result["final"]["modulus"])
    assert m == m1 * m2
    assert r % m1 == 0 and r % m2 == 1


def test_float_and_bool_rejected_by_api(client):
    for bad_period in [1.5, 1e30, True, "1.5", "abc"]:
        resp = client.post(
            "/api/proofs",
            json={
                "tracks": [{"id": "x", "period": bad_period, "phase": 0}],
                "cards": [],
            },
        )
        assert resp.status_code == 422, bad_period


def test_missing_and_deleted_proofs(client):
    assert client.get("/api/proofs/nope").status_code == 404
    assert client.post("/api/proofs/nope/verify", json={"revision": 1}).status_code == 404
    proof = create(client, compatible_proof())
    assert client.delete(f"/api/proofs/{proof['id']}").status_code == 204
    assert client.get(f"/api/proofs/{proof['id']}").status_code == 404
    assert client.get(f"/api/proofs/{proof['id']}/versions").status_code == 404

"""端到端冒烟：对运行中的 api / web 服务做黑盒检查。

所有期望值都在本脚本内用独立实现现算（扩展欧几里得 + 同余检验），
不与被测服务共享代码。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("API_URL", "http://api:8000").rstrip("/")
WEB = os.environ.get("WEB_URL", "http://web").rstrip("/")
EXAMPLES = os.environ.get("EXAMPLES_DIR", "/work/examples")

FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    mark = "✔" if cond else "✘"
    print(f"  {mark} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILED.append(name)


def req(method: str, url: str, body: object = None) -> tuple[int, object]:
    r = urllib.request.Request(
        url,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else None


def egcd(a: int, b: int) -> tuple[int, int, int]:
    if b == 0:
        return (a, 1, 0)
    g, u1, v1 = egcd(b, a % b)
    return (g, v1, u1 - (a // b) * v1)


def wait_ready(name: str, url: str, tries: int = 60) -> bool:
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    print(f"  ✘ {name} 未就绪：{url}")
    return False


def load_example(name: str) -> dict:
    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    print("── 等待服务就绪 ──")
    ok = wait_ready("api", f"{API}/api/health")
    ok = wait_ready("web", f"{WEB}/") and ok
    if not ok:
        return 1

    print("── web 静态站点与反代 ──")
    with urllib.request.urlopen(f"{WEB}/", timeout=10) as resp:
        html = resp.read().decode()
    check("web 返回单页应用", 'id="app"' in html)
    try:
        with urllib.request.urlopen(f"{WEB}/api/health", timeout=10) as resp:
            proxied = json.loads(resp.read())
        check("web 反代 /api 到 api 服务", proxied.get("status") == "ok")
    except Exception as exc:  # noqa: BLE001
        check("web 反代 /api 到 api 服务", False, str(exc))

    print("── 草稿 → 核验 → 版本 → 竞态 ──")
    compatible = load_example("compatible.json")
    s, proof = req("POST", f"{API}/api/proofs", compatible)
    check("创建草稿", s == 201 and proof["revision"] == 1)
    pid = proof["id"]

    s, v = req("POST", f"{API}/api/proofs/{pid}/verify", {"revision": 1})
    result = v["result"] if s == 200 else {}
    # 独立现算期望：x ≡ 1 (mod 4)，x ≡ 3 (mod 6)
    g, u, w = egcd(4, 6)
    expected_mod = 4 // g * 6
    expected_res = (1 + 4 * u * ((3 - 1) // g)) % expected_mod
    check(
        "兼容示例核验可解",
        result.get("status") == "solvable"
        and result["final"]["canonical_residue"] == str(expected_res)
        and result["final"]["modulus"] == str(expected_mod),
        json.dumps(result.get("final")),
    )

    s, r = req("PUT", f"{API}/api/proofs/{pid}", {**compatible, "revision": 1})
    check("保存草稿 revision 递增", s == 200 and r["revision"] == 2)
    s, r = req("POST", f"{API}/api/proofs/{pid}/verify", {"revision": 1})
    check("旧 revision 核验被拒", s == 409 and r.get("current_revision") == 2)
    s, r = req("PUT", f"{API}/api/proofs/{pid}", {**compatible, "revision": 1})
    check("旧 revision 保存被拒", s == 409 and r.get("current_revision") == 2)

    s, v1 = req("POST", f"{API}/api/proofs/{pid}/versions", {"revision": 2, "note": "smoke"})
    check("发布不可变版本", s == 201 and v1["version_no"] == 1)
    s, r = req("PUT", f"{API}/api/proofs/{pid}", {**compatible, "revision": 2})
    check("草稿继续前进", s == 200 and r["revision"] == 3)
    s, r = req("POST", f"{API}/api/proofs/{pid}/versions", {"revision": 2})
    check("旧 revision 发布被拒（版本竞态）", s == 409 and r.get("current_revision") == 3)
    s, r = req("POST", f"{API}/api/proofs/{pid}/versions/1/verify")
    check("不可变版本可核验且内容未变", s == 200 and r["result"]["status"] == "solvable")

    print("── 冲突 / 坏见证 / 非法依赖 ──")
    conflict = load_example("conflict.json")
    s, r = req("POST", f"{API}/api/compare", {"left": conflict, "right": conflict})
    check(
        "冲突示例判定无解",
        s == 200 and r["left"]["status"] == "unsolvable"
        and r["comparison"]["kind"] == "both_unsolvable",
    )

    bad = json.loads(json.dumps(compatible))
    bad["cards"][2]["witness"]["u"] = "0"  # 0·4+1·6=6 ≠ gcd(4,6)=2
    s, r = req("POST", f"{API}/api/compare", {"left": bad, "right": bad})
    fe = r["left"]["first_error"] if s == 200 else {}
    check(
        "坏见证被定位",
        fe.get("code") == "BAD_WITNESS" and fe.get("card_index") == 2,
        json.dumps(fe, ensure_ascii=False),
    )

    illegal = json.loads(json.dumps(compatible))
    illegal["cards"] = [
        {"type": "source", "track": "翅膀"},
        {"type": "normalize", "card": 5},  # 引用不存在的未来卡
    ]
    s, r = req("POST", f"{API}/api/compare", {"left": illegal, "right": illegal})
    fe = r["left"]["first_error"] if s == 200 else {}
    check(
        "非法依赖被定位",
        fe.get("code") == "BAD_REFERENCE" and fe.get("card_index") == 1,
        json.dumps(fe, ensure_ascii=False),
    )

    print("── 大整数与合并顺序对照 ──")
    big = load_example("bigint.json")
    s, r = req("POST", f"{API}/api/compare", {"left": big, "right": big})
    if s == 200 and r["left"]["status"] == "solvable":
        residue = int(r["left"]["final"]["canonical_residue"])
        modulus = int(r["left"]["final"]["modulus"])
        m1, m2 = 10**40 + 1, 10**40 + 3
        a1 = 123456789012345678901234567890
        a2 = 987654321098765432109876543210
        check(
            "40 位大整数精确核验",
            modulus == m1 * m2 and residue % m1 == a1 % m1 and residue % m2 == a2 % m2,
        )
    else:
        check("40 位大整数精确核验", False, json.dumps(r)[:200])

    ma = load_example("merge_order_a.json")
    mb = load_example("merge_order_b.json")
    s, r = req("POST", f"{API}/api/compare", {"left": ma, "right": mb})
    check(
        "两种合并顺序殊途同归",
        s == 200 and r["comparison"].get("equal") is True,
        json.dumps(r.get("comparison", {}), ensure_ascii=False),
    )
    s, r = req("POST", f"{API}/api/compare", {"left": ma, "right": conflict})
    check("可解与无解对照为 mixed", s == 200 and r["comparison"]["kind"] == "mixed")

    if FAILED:
        print(f"\n✘ 冒烟失败 {len(FAILED)} 项：{'、'.join(FAILED)}")
        return 1
    print("\n✔ 冒烟全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

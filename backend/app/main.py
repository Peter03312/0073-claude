"""FastAPI 入口：草稿（revision 乐观锁）+ 不可变版本 + 核验 + 对照。

并发约定：
- 所有写草稿/核验草稿/发布版本的请求都携带 revision；
  与服务器当前 revision 不符一律 409，拒绝核验也拒绝覆盖。
- 更新用单条 UPDATE ... WHERE revision = ? 原子完成，
  发布版本在 BEGIN IMMEDIATE 事务内取号，二者都不会出现竞态写穿。
"""
from __future__ import annotations

import os
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 任意精度整数的字符串化上限（默认 4300 位对“大整数”场景太紧）
sys.set_int_max_str_digits(200_000)

from .models import (  # noqa: E402
    CompareRequest,
    ProofCreate,
    ProofPayload,
    ProofUpdate,
    VerifyRequest,
    VersionCreate,
)
from .storage import Storage  # noqa: E402
from .verifier import compare_results, verify_proof  # noqa: E402


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="翻页动画同帧证明所", version="1.0.0")
    app.state.storage = Storage(db_path or os.environ.get("DB_PATH", "proofs.db"))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------- 工具

    def storage() -> Storage:
        return app.state.storage

    def not_found() -> HTTPException:
        return HTTPException(status_code=404, detail="证明不存在")

    def conflict(current: dict) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "revision 不符：草稿已被更新，请刷新后重试",
                "current_revision": current["revision"],
            },
        )

    def verify_payload(payload: ProofPayload) -> dict:
        return verify_proof(payload).to_wire()

    # ------------------------------------------------------------- 路由

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/proofs", status_code=201)
    def create_proof(body: ProofCreate) -> dict:
        title = (body.title or "").strip() or "未命名证明"
        return storage().create_proof(title, body.dump_tracks(), body.dump_cards())

    @app.get("/api/proofs")
    def list_proofs() -> list:
        return storage().list_proofs()

    @app.get("/api/proofs/{proof_id}")
    def get_proof(proof_id: str) -> dict:
        proof = storage().get_proof(proof_id)
        if proof is None:
            raise not_found()
        return proof

    @app.put("/api/proofs/{proof_id}")
    def update_proof(proof_id: str, body: ProofUpdate):
        title = (body.title or "").strip() or "未命名证明"
        status, value = storage().update_proof(
            proof_id, body.revision, title, body.dump_tracks(), body.dump_cards()
        )
        if status == "missing":
            raise not_found()
        if status == "conflict":
            return conflict(value)
        return value

    @app.delete("/api/proofs/{proof_id}", status_code=204)
    def delete_proof(proof_id: str):
        if not storage().delete_proof(proof_id):
            raise not_found()

    @app.post("/api/proofs/{proof_id}/verify")
    def verify_draft(proof_id: str, body: VerifyRequest):
        """核验草稿。revision 不符拒绝核验；可附带未保存的内容一起核验。"""
        proof = storage().get_proof(proof_id)
        if proof is None:
            raise not_found()
        if body.revision != proof["revision"]:
            return conflict(proof)
        if (body.tracks is None) != (body.cards is None):
            raise HTTPException(status_code=422, detail="tracks 与 cards 必须同时提供或同时省略")
        if body.tracks is not None and body.cards is not None:
            payload = ProofPayload(tracks=body.tracks, cards=body.cards)
        else:
            payload = ProofPayload.model_validate(
                {"tracks": proof["tracks"], "cards": proof["cards"]}
            )
        return {"revision": proof["revision"], "result": verify_payload(payload)}

    @app.post("/api/proofs/{proof_id}/versions", status_code=201)
    def publish_version(proof_id: str, body: VersionCreate):
        status, value = storage().create_version(proof_id, body.revision, body.note)
        if status == "missing":
            raise not_found()
        if status == "conflict":
            return conflict(value)
        return value

    @app.get("/api/proofs/{proof_id}/versions")
    def list_versions(proof_id: str) -> list:
        versions = storage().list_versions(proof_id)
        if versions is None:
            raise not_found()
        return versions

    @app.get("/api/proofs/{proof_id}/versions/{version_no}")
    def get_version(proof_id: str, version_no: int) -> dict:
        version = storage().get_version(proof_id, version_no)
        if version is None:
            raise not_found()
        return version

    @app.post("/api/proofs/{proof_id}/versions/{version_no}/verify")
    def verify_version(proof_id: str, version_no: int) -> dict:
        """核验不可变版本：内容固定，无需 revision。"""
        version = storage().get_version(proof_id, version_no)
        if version is None:
            raise not_found()
        payload = ProofPayload.model_validate(
            {"tracks": version["tracks"], "cards": version["cards"]}
        )
        return {"version_no": version_no, "result": verify_payload(payload)}

    @app.post("/api/compare")
    def compare(body: CompareRequest) -> dict:
        """对照两份证明（可为不同合并顺序）：各自核验后比较最终结论。"""
        left = verify_proof(ProofPayload(tracks=body.left.tracks, cards=body.left.cards))
        right = verify_proof(ProofPayload(tracks=body.right.tracks, cards=body.right.cards))
        return {
            "left": left.to_wire(),
            "right": right.to_wire(),
            "comparison": compare_results(left, right),
        }

    return app


app = create_app()

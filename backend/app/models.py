"""数据模型：API 边界的 JSON 结构。

大整数（周期、相位、Bézout 见证）在线上以十进制字符串传输，
避免 JavaScript 的 float64 精度损失；解析时接受 int 或十进制字符串，
拒绝 float / bool / 其他类型（禁止浮点进入核验流程）。
"""
from __future__ import annotations

import re
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt

_INT_RE = re.compile(r"^[+-]?\d+$")
MAX_INT_DIGITS = 10000  # 防御性上限，足够任何动画场景


def parse_big_int(value: object) -> int:
    """把 JSON 输入解析为任意精度整数，拒绝浮点与布尔。"""
    if isinstance(value, bool):
        raise ValueError("布尔值不是整数")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if _INT_RE.match(text):
            digits = text.lstrip("+-").lstrip("0") or "0"
            if len(digits) > MAX_INT_DIGITS:
                raise ValueError(f"整数位数超过上限 {MAX_INT_DIGITS}")
            return int(text)
        raise ValueError("字符串不是合法的十进制整数")
    raise ValueError("需要整数或十进制字符串，禁止浮点数")


BigInt = Annotated[int, BeforeValidator(parse_big_int)]
NonNegIndex = Annotated[StrictInt, Field(ge=0)]


class Track(BaseModel):
    """一条动画轨道：period 为正周期，phase 为零基相位。"""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=64)
    period: BigInt
    phase: BigInt

    def to_wire(self) -> dict:
        # 大整数以十进制字符串上线，前端不会被 float64 截断
        return {"id": self.id, "period": str(self.period), "phase": str(self.phase)}


class SourceCard(BaseModel):
    """引入一条轨道，得到同余式 x ≡ phase (mod period)。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["source"] = "source"
    track: str

    def to_wire(self) -> dict:
        return {"type": "source", "track": self.track}


class Witness(BaseModel):
    """Bézout 见证：需满足 u·m₁ + v·m₂ = gcd(m₁, m₂)。"""

    model_config = ConfigDict(extra="forbid")
    u: BigInt
    v: BigInt

    def to_wire(self) -> dict:
        return {"u": str(self.u), "v": str(self.v)}


class CombineCard(BaseModel):
    """合并两张来源不相交的前卡（中国剩余定理）。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["combine"] = "combine"
    left: NonNegIndex
    right: NonNegIndex
    witness: Witness

    def to_wire(self) -> dict:
        return {
            "type": "combine",
            "left": self.left,
            "right": self.right,
            "witness": self.witness.to_wire(),
        }


class NormalizeCard(BaseModel):
    """把前卡的余数化为最小非负剩余，模数与来源不变。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["normalize"] = "normalize"
    card: NonNegIndex

    def to_wire(self) -> dict:
        return {"type": "normalize", "card": self.card}


class ContradictionCard(BaseModel):
    """声明两张前卡互相冲突：仅当相位差不能被 gcd 整除时合法。"""

    model_config = ConfigDict(extra="forbid")
    type: Literal["contradiction"] = "contradiction"
    left: NonNegIndex
    right: NonNegIndex

    def to_wire(self) -> dict:
        return {"type": "contradiction", "left": self.left, "right": self.right}


Card = Annotated[
    Union[SourceCard, CombineCard, NormalizeCard, ContradictionCard],
    Field(discriminator="type"),
]


class ProofPayload(BaseModel):
    """一份证明的内容：轨道定义 + 按序排列的证明卡。"""

    model_config = ConfigDict(extra="forbid")
    tracks: list[Track] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)

    def dump_tracks(self) -> list[dict]:
        return [t.to_wire() for t in self.tracks]

    def dump_cards(self) -> list[dict]:
        return [c.to_wire() for c in self.cards]


class ProofCreate(ProofPayload):
    title: Optional[str] = None


class ProofUpdate(ProofPayload):
    """更新草稿必须携带当前 revision（乐观锁）。"""

    revision: StrictInt
    title: Optional[str] = None


class VerifyRequest(BaseModel):
    """核验草稿：revision 不符则拒绝。

    tracks/cards 可省略（核验服务器上存储的草稿），
    也可一起带上（核验编辑器里尚未保存的内容），但必须同时提供。
    """

    model_config = ConfigDict(extra="forbid")
    revision: StrictInt
    tracks: Optional[list[Track]] = None
    cards: Optional[list[Card]] = None


class VersionCreate(BaseModel):
    """从指定 revision 发布不可变版本。"""

    model_config = ConfigDict(extra="forbid")
    revision: StrictInt
    note: Optional[str] = None


class CompareSide(ProofPayload):
    """对照的一侧：允许携带 title 等展示信息（忽略）。"""

    title: Optional[str] = None


class CompareRequest(BaseModel):
    """对照两份证明（不同合并顺序 / 不同子集）。"""

    model_config = ConfigDict(extra="forbid")
    left: CompareSide
    right: CompareSide

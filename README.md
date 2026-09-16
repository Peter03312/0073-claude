# 同帧证明所 🎞️

> 校园动画社的翻页动画难题：每条轨道都是固定周期的翻页循环，
> **第几帧所有轨道再次同帧？** 不靠预览、不靠猜——把证明卡一张张摆出来，
> 让服务器用任意精度整数逐卡核验，第一处错误精确定位。

## 问题与数学背景

每条轨道给出同余式 `x ≡ phase (mod period)`（零基相位）。整组轨道同帧的帧号
就是同余方程组的解：

- **合并（中国剩余定理）**：`x ≡ a₁ (mod m₁)` 与 `x ≡ a₂ (mod m₂)` 有解当且仅当
  `a₁ ≡ a₂ (mod g)`，其中 `g = gcd(m₁, m₂)`。给定 **Bézout 见证**
  `u·m₁ + v·m₂ = g`，解为
  `x ≡ a₁ + m₁·u·(a₂−a₁)/g (mod lcm(m₁, m₂))`。
- **冲突**：相位差不能被 `gcd` 整除时，两条同余式永不同帧——任一不相容子集
  都足以证明整题无解。
- **规范化**：把余数化为最小非负剩余（`a mod m`），不同合并顺序才能按
  “规范余数 + 模最小公倍数”比较出殊途同归。

核验器只做 `gcd`、乘法和整除等 **O(位数)** 的整数运算：**禁止浮点**
（`2⁵⁴+1` 与 `2⁵⁴+2` 在 float64 下无法区分），也**禁止枚举到最小公倍数**
（示例里 40 位周期的 lcm 有 81 位）。

## 证明卡 JSON

```jsonc
{
  "tracks": [
    { "id": "翅膀", "period": "4", "phase": "1" },   // 正周期、零基相位
    { "id": "尾巴", "period": "6", "phase": "3" }
  ],
  "cards": [
    { "type": "source", "track": "翅膀" },            // #0 引入轨道
    { "type": "source", "track": "尾巴" },            // #1
    { "type": "combine", "left": 0, "right": 1,       // #2 合并两张来源不相交的前卡
      "witness": { "u": "-1", "v": "1" } },           //     Bézout 见证 u·m₁+v·m₂=gcd
    { "type": "normalize", "card": 2 }                // #3 化为最小非负剩余
  ]
}
```

| 卡类型 | 字段 | 合法性 |
| --- | --- | --- |
| `source` | `track` | 轨道已定义；得 `x ≡ phase (mod period)` |
| `combine` | `left`,`right`,`witness{u,v}` | 两前卡均为同余式、**来源不相交**、`u·m₁+v·m₂=gcd(m₁,m₂)` 精确成立、相位差可被 `gcd` 整除 |
| `normalize` | `card` | 前卡为同余式；只化为最小非负剩余，模数与来源不变 |
| `contradiction` | `left`,`right` | 两前卡均为同余式，且相位差**不能**被 `gcd` 整除 |

- 引用一律指向**严格更早**的卡（零基序号），否则 `BAD_REFERENCE`。
- 大整数（周期、相位、见证、余数、模数）在线上**一律用十进制字符串**，
  前端不会被 float64 截断；服务端接受字符串或 JSON 整数，拒绝浮点与布尔。
- 判定结果：`solvable`（末卡同余式覆盖全部轨道，给出首次同帧帧号与循环周期）、
  `unsolvable`（末卡为冲突卡，其来源即不相容子集）、`incomplete`（未覆盖全部轨道）、
  `invalid`（`first_error` 定位首个非法依赖或算术步骤）、`empty`。

更多示例见 [`examples/`](examples/)：`compatible.json`、`conflict.json`、
`bigint.json`（40 位周期）、`merge_order_a/b.json`（同一组轨道的两种合并顺序）。

## 快速开始（Docker Compose）

```bash
docker compose up --build web api     # 常驻服务：web(8080) + api(8000)
# 打开 http://localhost:8080
```

宿主机端口可用环境变量覆盖：

```bash
WEB_PORT=9000 API_PORT=9001 docker compose up --build web api
```

一次性验证（后端测试 → 前端构建 → 端到端冒烟，完成后自动退出）：

```bash
docker compose up --build --exit-code-from verify
docker compose down
```

## 本地开发

```bash
# 后端（Python 3.11+）
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload          # http://localhost:8000

# 前端（Node 20+）
cd frontend
npm install
npm run dev                            # http://localhost:5173，/api 自动代理到 8000

# 测试
cd backend && python -m pytest tests -q
cd frontend && npm run build           # vue-tsc 类型检查 + 产物构建
```

## API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/proofs` | 新建草稿（revision 从 1 开始） |
| `GET` | `/api/proofs` / `/api/proofs/{id}` | 列表 / 草稿详情 |
| `PUT` | `/api/proofs/{id}` | 携带 `revision` 更新草稿；不符则 **409** |
| `DELETE` | `/api/proofs/{id}` | 删除草稿及其版本 |
| `POST` | `/api/proofs/{id}/verify` | 携带 `revision` 核验；**revision 不符拒绝核验（409）**；可附带未保存的 `tracks/cards` 一并核验 |
| `POST` | `/api/proofs/{id}/versions` | 从指定 `revision` 发布**不可变版本**；不符则 409 |
| `GET` | `/api/proofs/{id}/versions[/{n}]` | 版本列表 / 详情 |
| `POST` | `/api/proofs/{id}/versions/{n}/verify` | 核验不可变版本（内容固定，无需 revision） |
| `POST` | `/api/compare` | 对照两份证明：各自核验后比较最终结论（规范余数 + 模最小公倍数） |

### 并发与一致性设计

- **乐观锁**：更新/核验/发布都携带 `revision`；更新用单条
  `UPDATE ... WHERE revision = ?` 原子完成，并发写只有一个成功，其余 409。
- **不可变版本**：版本表只插不改，`(proof_id, version_no)` 主键，
  取号在 `BEGIN IMMEDIATE` 事务内完成。
- **迟到响应不得覆盖新稿**：前端为每次核验/保存请求递增序号，
  只有最新一次响应允许落地；服务端再以 409 兜底。

## 页面

- **编辑器**：轨道表、证明卡列表（合并卡可一键“自动填见证”，前端 BigInt
  扩展欧几里得）、SVG 证明图（节点=卡、边=依赖、首错红框、结论绿框），
  图、步骤列表、来源三者联动高亮；保存/发布遇 409 给出冲突提示。
- **对照视图**：左右各选一份草稿或不可变版本，并排渲染两张 SVG 证明图，
  顶部给出“殊途同归 / 相容 / 矛盾 / 一解一否”的结论。

## 测试

`backend/tests/`（35 项，全部通过）：

- **兼容**：随机系统与暴力枚举对照（仅测试枚举小周期，核验器本身不枚举）。
- **冲突**：`contradiction` 合法性；对不相容卡 `combine` 必拒。
- **坏见证**：`u·m₁+v·m₂ ≠ gcd` 精确拒绝。
- **非法依赖**：引用未来/自身、合并冲突卡、来源相交、未知轨道。
- **大整数**：`2⁵⁴+1` 与 `2⁵⁴+2`（float64 不可区分）必须判相容；
  40 位十进制字符串直接核验；同模相差 1 必判冲突。
- **版本竞态**：并发写只有一个成功；旧 revision 的核验/保存/发布全部 409；
  版本发布后内容冻结。

测试的期望值均用独立实现现算（扩展欧几里得、暴力枚举），不硬编码答案。

## 目录结构

```
├── docker-compose.yml      # web / api 常驻服务 + verify 一次性服务
├── backend/                # FastAPI + SQLite
│   ├── app/models.py       #   线格式模型（大整数十进制字符串）
│   ├── app/verifier.py     #   任意精度逐卡核验（纯标准库）
│   ├── app/storage.py      #   草稿乐观锁 + 不可变版本
│   ├── app/main.py         #   路由
│   └── tests/              #   pytest：35 项
├── frontend/               # Vue 3 + TypeScript + Vite
│   └── src/components/     #   ProofGraph(SVG) / ResultView / CardEditor
├── verify/                 # 一次性服务：pytest → 前端构建 → 冒烟
└── examples/               # 兼容 / 冲突 / 大整数 / 两种合并顺序
```

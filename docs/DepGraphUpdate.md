# 1. 目標與非目標

## 1.1 目標（Goals）

1. **多語言語法正確**的依賴擷取：以 tree-sitter 解析檔案，抽取 import/include/use/require 等「引用關係」。
2. **可用於 refactor 的 internal 依賴圖**：對能解析到 repo 內檔案的引用，輸出 `dst_resolved_path`，支援 reverse deps / impact set。
3. **可稽核（evidence）**：每條 edge 帶來源位置（line/col range）與 `dst_raw`，下游或人可回查。
4. **語言無關 schema**：下游不需要懂 Python/TS/Go 的 AST 節點，統一吃同一種 edge 結構。
5. **可控的工程複雜度**：先把價值最大的「import-level graph」做到可用，避免陷入語意解析的高成本泥沼。

## 1.2 非目標（Non-goals）

- 不保證「runtime 真實依賴」100% 精準（動態 import、macro、re-export 等）。
- 不做「call graph（誰呼叫了哪個函式/方法）」或完整 symbol resolution。
- 不整合每個語言的 build system / language server（例如 tsc、gopls、rust-analyzer、jdtls）做語意級解析。
- 不評估條件編譯（C/C++ preprocessor）展開後的真實 include 結果（可留作低信心/未知類型）。

---

# 2. 新版本輸出物（Artifacts）與下游可用資訊

> 你要求「不需要保留舊版」：因此新版本直接把舊 DepGraphL0 替換成 DepGraph（同檔案名亦可），下游統一讀新 schema。
>

## 2.1 必出 Artifact（MUST）

### A) `dep_graph.json`

- 全 repo 依賴圖（檔案節點 + 依賴邊）
- 每條邊含：語言、引用種類、raw/norm specifier、internal resolve（若可）、range、confidence

### B) `dep_reverse_index.json`

- 反向索引（refactor 最常用）：
    - key = `dst_resolved_path`（internal）或 `dst_norm`（external）
    - value = 所有引用它的 `src` 與 range（或 edge_id）

> 下游用途：快速回答「X 被哪些檔案依賴？」（reverse deps）、影響分析（impact analysis）起點。
>

### C) `dep_metrics.json`

- per-file：fan-in/fan-out、是否在 cycle、SCC id、內外部依賴比
- per-folder（可選）：跨資料夾依賴數、layer violation 統計

> 下游用途：排序 refactor 優先級（高 fan-in、高 cycle 節點先處理）。
>

### D) `external_deps_inventory.json`

- external dependency 的聚合清單（dst_norm → count、top importers）

> 下游用途：SBOM/安全掃描/依賴盤點，或判斷外部依賴耦合風險。
>

---

# 3. 資料模型（Schema）— 直接替換現有 types

你目前 `DepEdge`/`DepGraphL0` 太薄，無法支撐「internal resolve + evidence」。
ingestion_types

新版本做法：*直接改寫 ingestion_types.py 的 Dep 型別**（不保留 L0/L1 兩套）。

## 3.1 新增/改寫的核心型別

### 3.1.1 `DepRange`

- `start_line: int`（1-based）
- `start_col: int`（0-based）
- `end_line: int`
- `end_col: int`

### 3.1.2 `DepDstKind`（Enum）

- `internal_file`：可 resolve 到 repo 內檔案
- `external_pkg`：外部套件/第三方/遠端 module path
- `stdlib`：可高信心判定為標準庫（可選能力；不確定就歸 external_pkg）
- `relative`：相對路徑/相對匯入但暫未 resolve
- `unknown`：無法分類

### 3.1.3 `DepRefKind`（Enum）

通用引用種類（語言無關）：

- `import`：語言原生 import（Python/JS/TS/Go/Java）
- `include`：C/C++ include
- `use`：Rust use
- `require`：JS CommonJS require
- `dynamic_import`：JS `import()` / Python importlib（可先支援 JS）
- `other`：其他語法型引用（預留）

### 3.1.4 `DepEdge`（全面替換）

必填欄位（MUST）：

- `src: str`（repo file path，沿用你現在 node_id = path 的慣例）depgraph
- `lang: str`（例如 `python|ts|js|go|java|rust|c|cpp`）
- `ref_kind: DepRefKind`
- `dst_raw: str`（原始 specifier：例如 `"react"`、`pkg.foo`、`<stdio.h>`）
- `dst_norm: str`（正規化 key：用於聚合/索引；規則見 §5）
- `dst_kind: DepDstKind`
- `range: DepRange`
- `confidence: float`（0~1；規則見 §6）

選填欄位（SHOULD/OPTIONAL）：

- `dst_resolved_path: str | None`（internal_file 時 SHOULD 有）
- `symbol: str | None`（from-import / named import；不做 call graph，但保留符號名可幫助搜尋）
- `is_relative: bool | None`
- `extras: dict[str, Any] = {}`（語言特有資訊：python_level、ts_is_type_only、c_include_kind...）

### 3.1.5 `DepNode`（小改）

- 保留：
    - `node_id: str`
    - `path: str`
    - `kind: str = "file"`
- 建議新增（OPTIONAL）：
    - `lang: str | None`
    - `ext: str | None`

### 3.1.6 `DepGraph`

- `nodes: list[DepNode]`
- `edges: list[DepEdge]`
- 建議加：
    - `version: str = "2"`（或任意固定字串）
    - `generated_at: datetime`（可選）

---

# 4. 模組邊界與責任分工（最小可落地）

你目前 `DepGraphExtractor` 一個檔案做全部（掃檔、regex、建 edges）。
depgraph

新版本建議最小拆分（避免過度設計，但保 SOLID）：

## 4.1 `depgraph/`（或維持單檔但用 class 分段也可）

1. `language_detect.py`
    - `detect_language(path) -> lang_id | None`
    - 只做 extension-based mapping（先滿足 80%）
2. `ts_parser.py`
    - Tree-sitter parser 管理（載入 grammar、parse bytes）
    - `parse(code: bytes, lang_id) -> tree`
3. `queries/`（每語言一份 query）
    - `python.scm`, `javascript.scm`, `typescript.scm`, `go.scm`, `java.scm`, `rust.scm`, `c.scm`, `cpp.scm`
    - 只 capture 你需要的節點：import/include/use/require 的目標字串與位置
4. `extractors/`
    - `extract_edges(tree, code, lang_id, src_path) -> list[RawEdge]`
    - RawEdge 至少含：`dst_raw`, `range`, `ref_kind`, `symbol?`, `extras?`
5. `normalizers/`
    - `normalize(raw_edge, lang_id) -> (dst_norm, dst_kind_guess, is_relative, confidence_base, extras_merge)`
    - 只做「字串正規化」與初步分類，不做 repo resolve
6. `resolvers/`
    - `build_repo_index_maps(repo_index) -> maps`
    - `resolve_internal(src_path, lang_id, dst_norm, raw_edge) -> dst_resolved_path | None`
    - 只做 best-effort：Python module mapping + JS/TS relative path resolution（先最有價值的兩類）
7. `builder.py`
    - 組裝 `DepGraph(nodes, edges)`、排序、去重、輸出 reverse index / metrics

    > 你也可以先維持單一 depgraph.py，但至少在 class/函式層面維持這些邊界，避免 extractor 變成巨石。
    >

---

# 5. 正規化與 internal resolve 規則（必須明確，否則下游不可用）

## 5.1 通用規則（所有語言）

- `dst_raw`：保持語法上抽到的原始引用（去掉外層引號可接受，但要一致）
- `dst_norm`：用於聚合/索引的 key，**必須 deterministic**
- `dst_kind`：依規則判斷（internal_file 需要 resolver 支援）
- `range`：來源位置（1-based line；col 0-based）
- `edge 去重 key`（建議）：

    `(src, ref_kind, dst_norm, dst_resolved_path or "", symbol or "", range.start_line, range.start_col)`

    目標是避免同一行/同一引用被重複記錄。


## 5.2 Python 正規化 + resolve（MUST）

### 抽取

- `import x.y` → `dst_raw="x.y"`, `dst_norm="x.y"`, `ref_kind=import`
- `from x.y import z as a` → `dst_raw="x.y"`, `symbol="z"`, `dst_norm="x.y"`, `ref_kind=import`
- `from .utils import foo`：
    - `dst_raw=".utils"`, `extras.python_level=1`, `is_relative=True`
    - `dst_norm` 先以「相對表示」保存，例如：`REL1:utils`（或你自訂格式，但必須固定）

### repo internal resolve

建立 mapping：

- `pkg/foo.py` → module `pkg.foo`
- `pkg/__init__.py` → module `pkg`
- 產生 `module_to_path` 與 `path_to_module`

resolve 策略：

- 絕對 import：`dst_norm` 若在 `module_to_path` → `dst_kind=internal_file` 並填 `dst_resolved_path`
- 相對 import：用 `src_path` 所在 package 深度 + `python_level` 回退，再拼接 module name，嘗試命中 `module_to_path`

> 注意：from pkg import foo 可能是 pkg/__init__.py re-export 或 pkg/foo.py。
>
>
> 本版**不做語意判斷**；策略：先嘗試 `pkg.foo`，再 fallback `pkg`，confidence 需下調（見 §6）。
>

## 5.3 JS/TS 正規化 + resolve（MUST）

- `import x from "react"` → `dst_norm="react"`, external_pkg
- `import x from "../utils"` → `dst_norm="../utils"`, relative
- `require("lodash")` → `ref_kind=require`, `dst_norm="lodash"`

resolve（只做 relative path）：

- 若 `dst_raw` 以 `./` 或 `../` 開頭：
    - 以 `src_path` 目錄為基準做 path resolve
    - 嘗試副檔名補全：`.ts/.tsx/.js/.jsx`
    - 嘗試 index 檔：`/index.ts` 等
    - 命中 repo 檔案則 `dst_kind=internal_file` + `dst_resolved_path`

> 本版不要求支援 tsconfig paths / package.json exports（成本太高）。可把這些命中的 specifier 視為 external_pkg 或 unknown。
>

## 5.4 Go/Java/Rust/C/C++（語法抽取 MUST，resolve OPTIONAL）

- Go：
    - `import "fmt"`、`import "github.com/a/b"` → external_pkg 或 stdlib（若你願意做 stdlib 名單）
- Java：
    - `import java.util.List`、`import com.myco.Foo` → 多數 external/stdlib/unknown（internal resolve 成本高，先不做）
- Rust：
    - `use crate::x::y` / `use std::...` → 可先分類 stdlib/unknown；internal resolve 需要 cargo context，先不做
- C/C++：
    - `#include <stdio.h>` vs `#include "my.h"`：可在 `extras.c_include_kind` 標記 angle/quote
    - `"my.h"` 是否 internal：若你願意，可做「在 repo 內搜尋同名 header」的 best-effort resolve（但風險高，建議先 unknown/relative）

---

# 6. Confidence 規則（必須定義，否則下游難用）

本版把 confidence 當作「語法與 resolve 的可靠度」，不是 runtime 真實性。

建議基準：

- tree-sitter 靜態 import/include/use：`0.9`
- JS require：`0.85`
- dynamic import（JS import()）：`0.6`
- Python `from pkg import foo` 且只能 resolve 到 `pkg`（非 `pkg.foo`）：`0.7`
- 相對匯入但 resolve 失敗：`0.5`
- parser 失敗且 fallback（若你保留 fallback）：`0.3`

> 你舊版固定 0.5。depgraph
>
>
> 新版信心度能讓下游做：過濾低信心邊、或優先人工檢查。
>

---

# 7. 實作需求（工程面）

## 7.1 依賴（Dependencies）

- Python tree-sitter bindings（`tree_sitter`）
- grammar 來源：
    - 選項 A（快）：使用現成 bundle（例如 `tree_sitter_languages` 類型的套件）
    - 選項 B（可控）：vendor 各語言 grammar，建置成 shared library（CI 較麻煩但可控）

你要的「最划算版本」通常用 A 先落地，再視穩定性決定要不要轉 B。

## 7.2 效能與 deterministic 輸出（MUST）

- 檔案遍歷順序固定（字典序）
- edges 排序固定（`src`, `ref_kind`, `dst_norm`, `range`）
- JSON 輸出 deterministic（避免每次 diff 很大）

## 7.3 錯誤處理（MUST）

- 單檔 parse 失敗不可中止整體 ingestion
- 要記錄：
    - 失敗檔案、語言、錯誤訊息摘要
- 建議輸出 `logs/dep_graph/errors.jsonl`

## 7.4 測試（SHOULD）

- 每語言至少 3 個 snippet fixture：
    - 正常 import/include
    - 多行/括號/區塊（Go import block、Python from-import multi）
    - 相對路徑（JS/TS）與相對匯入（Python）

---

# 8. 與舊版相比的 Diff 與影響面（Migration Impact）

## 8.1 資料模型差異（breaking）

舊 `DepEdge`：

- `{src, dst, kind="import", confidence?}` ingestion_types

新 `DepEdge`（breaking）：

- `dst` 拆成：`dst_raw + dst_norm + dst_kind + dst_resolved_path?`
- 必須新增：`lang + ref_kind + range + confidence`
- 可選：`symbol + is_relative + extras`

=> **所有下游讀取 `DepEdge.dst` 的地方都要改**（改讀 `dst_resolved_path` 或 `dst_norm`，視 use-case）。

## 8.2 語意差異（重要）

- 舊版：regex 行級掃描，假陽/假陰都高，且無位置資訊。depgraph
- 新版：tree-sitter 語法解析 + range evidence，準確性與可稽核性提升；但仍非語意解析（仍需保守看待 dynamic/re-export）。

## 8.3 行為差異（預期）

- edges 數量可能**增加**（以前漏抓的多行/區塊 import 會被抓到）
- edges 可能**更乾淨**（註解/字串誤抓下降）
- internal edges 出現：`dst_resolved_path` 能讓 refactor/impact 分析真正落地

---

# 9. 你沒明講但必須理解的「隱含規格」與風險點

1. **tree-sitter 是 CST/語法樹，不是語意 AST**

    它回答的是「語法上寫了什麼引用」，不是「runtime 真依賴」。因此 confidence/edge_kind 必須存在，否則下游會誤用。

2. **internal resolve 永遠是 best-effort**

    尤其 Python package layout、namespace packages、JS bundler alias，會造成「看起來 internal 但 resolve 不到」或反之。

3. **refactor plan 最需要的是 reverse deps（誰依賴我）**

    這也是為何 `dep_reverse_index.json` 應列為 MUST：它是最直接的下游加速結構。

4. **不要把 schema 設計成「通用 AST」**

    多語言 AST 統一成本極高且下游難用。通用 dependency fact schema 才是高 ROI。

5. **輸出要 deterministic**

    否則你每次跑 ingestion 都會有巨大 diff，會污染後續 pipeline（尤其 evidence / PR review）。


---

# 10. 交付驗收條件（Acceptance Criteria）

## A) Schema / Validation

- `dep_graph.json` 必須通過 Pydantic validation（新 `DepGraph/DepEdge`）
- 每條 edge 必須有：`src/lang/ref_kind/dst_raw/dst_norm/dst_kind/range/confidence`

## B) 功能

- 對 Python 檔：
    - `import` 與 `from ... import ...` 皆可擷取
    - 相對匯入 `from .x import y` 能產生 `extras.python_level` 與 `is_relative`
    - internal resolve 能把 repo 內 module 解析成 `dst_resolved_path`（至少涵蓋 `pkg/foo.py`、`pkg/__init__.py`）
- 對 JS/TS 檔：
    - `import ... from "..."`、`require("...")` 能擷取
    - relative path 能 resolve 成 `dst_resolved_path`（含副檔名與 index 嘗試）

## C) Artifact

- `dep_reverse_index.json` 存在且可用：任選 10 個 internal 檔案，均能查出至少 0..N 個引用者（空集合也要能表示）

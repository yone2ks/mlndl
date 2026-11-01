# ADR-0001: `attaches_to` の使い分け基準

- **Status**: Accepted
- **Date**: 2026-05-27
- **Deciders**: mlndl-spec-architect (Pass C)
- **Pass**: C (再設計後の最終版)
- **Supersedes**: drafts/0001-attaches-to.md
- **Amended by**: ラウンド4 Pass C (2026-10-15) — D8 を追加。参照先の種類をキーで示し、`{interface:}` を L1 IF 専用に戻した
  ([round4-evaluation](evaluations/round4-evaluation.md) 論点 A、ユーザー判断)
  / [ADR-0010](0010-control-plane-separation.md) (2026-11-01) — `{link:}` キーを削除 (D8 の改訂)

## Context

MLNDL は RFC 8345 のマルチレイヤトポロジーモデルを継承し、下位層が上位層の物理基盤となる「supporting 関係」を表現する必要がある。RFC 8345 は層ごとに 3 つの別フィールドを持つ:

- `supporting-node` (ノードの下位対応)
- `supporting-termination-point` (TP=インターフェースの下位対応)
- `supporting-link` (リンクの下位対応)

MLNDL は DSL としての書きやすさを優先するため、これらを単一フィールド `attaches_to` に統合する。

### Pass B での主要指摘

1. **`layer` フィールドの冗長性**: ADR-0002 (Pass C) でグローバル一意 ID が確定したため、`{layer: layer1, interface: leaf1-swp51}` の `layer` フィールドが不要ではないか
2. **shape-based discriminator の脆さ**: `str | AttachesToInterface | AttachesToLink` の Union は形状ベース判別であり pydantic v2 で不安定になりうる
3. **自己参照 / 上位層 attach / 同層 attach** の severity が未整理
4. **multi-homing** (dvSwitch の複数 vmnic 同時 attach) の Phase 1 での扱いが未定

### 前提 (Pass C 確定事項)

- **ADR-0002 (Pass C)**: MLNDL の ID はトポロジー文書内でグローバル一意。正規表現 `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`。ノード・インターフェース・リンク・VRF・VLAN・VNI など全エンティティが単一 ID 空間を共有する
- **ADR-0002 D8**: バリデーション severity (`error / warning / info`) の共通定義はこちらを参照
- mlndl は RFC 8345 を「圧縮した」表現を採用するが、エクスポーター `exporter/rfc8345.py` で復元できることを必須要件とする

## Decision

### D1. `attaches_to` は単一フィールドで supporting 関係を表現する

ノード・インターフェース・リンクの 3 種類の supporting 関係を、すべて `attaches_to` という 1 フィールドで表現する。RFC 8345 の 3 フィールド分割は採用しない (記述量増・論文継承の趣旨に反する)。

### D2. `layer` フィールドを廃止し、タグ付き Union を採用

ADR-0002 (Pass C) によりグローバル一意 ID が保証されるため、`layer` フィールドは冗長である。`attaches_to` の正規形は **キー名を discriminator とするタグ付き Union** とする:

```yaml
# ノード参照 (例: VM がホスト上で動く)
attaches_to:
  node: eve-server

# インターフェース参照 (例: 論理 IF が物理ポートで実現される)
attaches_to:
  interface: leaf1-swp51

# リンク参照 (例: BGP セッションが物理リンク上を流れる)
# → ADR-0010 D7 (2026-11-01) で削除。セッションの通り道は update_source の L3 IF から導く (D8 の改訂を参照)
attaches_to:
  link: link-spine1-leaf1
```

各形式はキーが 1 つだけであり、キー名 (`node` / `interface` / `link`) がそのまま discriminator として機能する。pydantic v2 では `Annotated[Union[...], Discriminator(...)]` でタグベース判別を使い、shape-based discriminator の脆さを回避する。

pydantic 型定義:

```python
from typing import Annotated, Union
from pydantic import BaseModel, ConfigDict, Discriminator, field_validator

ATTACHES_TO_KEYS = {"node", "interface", "link"}

def _attaches_to_tag(v):
    """discriminator callable — キー名でモデルを特定する。"""
    if isinstance(v, dict):
        keys = set(v.keys()) & ATTACHES_TO_KEYS
        if len(keys) != 1:
            return None  # pydantic が UnionTag エラーとして扱う
        return next(iter(keys))
    return getattr(v, "_tag", None)  # 既に BaseModel に解決済みの場合

class AttachesToNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node: str          # ノード ID

class AttachesToInterface(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interface: str     # インターフェース ID

class AttachesToLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    link: str          # リンク ID

AttachesToObject = Annotated[
    Union[AttachesToNode, AttachesToInterface, AttachesToLink],
    Discriminator(_attaches_to_tag)
]

# str は文字列糖衣 (D3 参照)。field_validator(mode="before") で Union 解決前に正規化する。
AttachesTo = Union[str, AttachesToObject]
```

`extra="forbid"` により `{node: x, interface: y}` や `{layer: layer1, interface: x}` のような不正な複数キー入力はパース段階で error になる。旧形式 (`layer` フィールドあり) のマイグレーション時に「ADR-0001 (mlndl 1.0) で廃止されました。`{interface: ...}` に書き換えてください」という明示的なエラーメッセージを `model_validator(mode="before")` で出力することを推奨する。

### D3. 文字列糖衣はノード参照に限定

手書き YAML の利便性のため、`attaches_to: eve-server` (文字列) を引き続き許容する。ただし:

- **文字列が許されるのはノード参照のみ** (`attaches_to: {node: eve-server}` と等価)
- インターフェース・リンクを指す場合は必ずオブジェクト形式を使う。理由: グローバル一意 ID 空間では文字列だけでは「ノード ID か IF ID か」をパース段階で判別できない
- **生成系 (アダプター・エクスポーター) は必ずオブジェクト形式で出力する**。手書き YAML のみ文字列糖衣を許容する

パーサーは `field_validator(mode="before")` で `str → {"node": v}` に展開する。Union 解決の**前**に正規化することで、内部表現は常に `AttachesToObject` のみとなる。エクスポーターは外部向けに `AttachesTo` 型を公開するが、内部ロジックは常に `AttachesToObject` を扱う。

### D4. multi-homing は Phase 1 ではスカラーのみ

`attaches_to` は単一の supporting 関係を表す。dvSwitch のように複数物理ポートに同時 attach する状況は **Phase 2 以降** で `list[AttachesToObject]` への拡張を検討する。Phase 1 での回避策:

- `port_channels` (LAG) を流用する
- 論理 IF を複数定義してそれぞれに `attaches_to` を持たせる

いずれも Phase 1 の記述能力として十分である。

### D5. レイヤー方向の制約

| 参照方向 | 許容/禁止 | 根拠 |
|---------|---------|------|
| 同層または下位層への attach | 許容 | supporting 関係の本来の方向 |
| 上位層への attach | **error** | 物理 NIC (L1) が論理 IF (L3) に attach するのは supporting の逆方向 |
| 同層内 attach | 許容 (info) | vswitch が hypervisor に attach する等、実在する構成 |
| ループ (A→B→A) | **error** | 循環する supporting 関係は無意味 |

上位層チェックは Phase 2 でレイヤー定義が整った段階で実装する。Phase 1 では参照先 ID の存在確認のみ。

### D6. バリデーションチェック一覧

severity の定義は **ADR-0002 D8** を参照 (要約: `error` = 検証失敗・例外送出、`warning` = 続行可・診断メッセージ、`info` = 通知のみ)。

| 状況 | Severity |
|------|---------|
| 未定義 ID を参照 | `error` |
| 自己参照 (`node-a.attaches_to == {node: "node-a"}`) | `error` |
| 上位層への attach (Phase 2 以降) | `error` |
| `attaches_to` チェーンの循環 | `error` |
| ID 種別の不一致 (`node` キーに IF ID を書いた等) | `error` |
| 旧形式 `{layer: ..., interface: ...}` の入力 | `error` (「`layer` フィールドは ADR-0001 (mlndl 1.0) で廃止されました。`{interface: ...}` に書き換えてください」) |
| 同層 attach | `info` |
| 文字列形式の使用 (オブジェクト推奨) | `info` |

### D7. RFC 8345 エクスポーターの責務

`exporter/rfc8345.py` は `attaches_to` を **3 フィールドに分解して出力する**。`layer` フィールドを mlndl が持たなくても、参照先 ID がどのレイヤーのコレクションに登録されているかをエクスポート時に逆引き (グローバル一意 ID なので O(1)) することで層情報を復元できる。RFC 8345 への往復変換は成立する。

### D8. 参照先の種類はキーで示す (ラウンド4 Pass C で追加, 2026-10-15)

D2 のキーに `lag` / `vlan` / `subinterface` を加え、**`interface` は L1 インターフェース専用**とする。

| キー | 参照先 |
|---|---|
| `node` | `layer1.nodes` |
| `interface` | `layer1.interfaces` (L1 IF のみ) |
| `lag` | `layer1.lag` |
| `vlan` | `layer2.vlans` |
| `subinterface` | `layer2.subinterfaces` |
| ~~`link`~~ | ~~`layer1.links`~~ — ADR-0010 で削除 (下記) |

どのキーを書けるかはエンティティごとに決め、**スキーマ (型) で制限する**。書けないキーはパース段階で error になる。

| `attaches_to` を持つエンティティ | 書けるキー |
|---|---|
| `layer1.nodes` / `layer1.interfaces` | 文字列 (ノード) / `node` / `interface` (D1〜D7 のまま。`link` は ADR-0010 で削除) |
| `layer2.subinterfaces` | `interface` / `lag` |
| `layer3.interfaces` | `interface` / `lag` / `vlan` / `subinterface` |

VLAN のポート (`layer2.vlans[].trunk_ports` / `access_ports`) も同じ考え方で `{interface:}` / `{lag:}` と書く (ADR-0013 D1)。

**経緯**: ADR-0012 / 0013 (Pass A) は `{interface: X}` の X に L1 IF / LAG / VLAN / サブ IF のどれでも書けるようにし、
どれを受け付けるかを参照元ごとの表で管理した。ラウンド4 Pass B で、(1) 同じキーが参照元によって違う ID 空間を引くのは
D2「キー名が discriminator」に反する、(2) YAML を見ても何を指しているかが分からない (試し書きで実際に迷った)、
(3) `layer2.bridges` などを足すたびに表が広がる、と指摘された。キーを分ければ受付の表がスキーマそのものになり、
新しい種類 (例: `{bridge:}`) はキーを 1 つ足すだけで済む。

**旧形式の扱い**: `{interface: X}` で X が LAG / VLAN / サブ IF を指す書き方は、ndl_version 1.x の間だけ受け付ける。
validator が X の種類を引き、`{lag: X}` などに書き換えるよう **warning** を出す (`--strict` では error)。
この読み替えは ID のグローバル一意性 (ADR-0002 D5) に頼るので、L1 IF / LAG / VLAN / サブ IF の ID 重複は引き続き error。

キーと ID の種類が食い違う参照 (例: `{lag: vlan-100}`) は未定義の参照として error にし、正しいキーをメッセージで示す。

**改訂 (ADR-0010, 2026-11-01)**: `{link:}` キーを削除する。使い道は BGP セッション (`layer3.routing_adjacencies[].attaches_to`) だけだったが、
ADR-0010 D7 でセッションの通り道は `update_source` の L3 IF の `attaches_to` から導くことにし、セッションの `attaches_to` を廃止した
(書くと同じ事実を 2 か所に書くことになり、ループバックで張りながら直結のリンクを指す食い違いも通っていた)。
L1 ノード・L1 IF がリンクの上で実現される場面はないので、キーごと削除する。必要になれば加算的に戻す。実装は ADR-0010 の実装と同時に行う。

## Consequences

### 良い影響

- **`layer` フィールドの冗長性排除**: ADR-0002 のグローバル一意 ID の恩恵を最大化。二重情報を排除
- **型安全性向上**: タグ付き Union により pydantic v2 が静的に型を判別。shape-based discriminator の脆さを回避
- **書きやすさの維持**: ノード参照の文字列糖衣を残したため手書き YAML の簡潔さを保持
- **RFC 8345 への可逆性**: ID 逆引きで層復元が成立し、情報損失なし

### 悪い影響 / トレードオフ

- **既存サンプルの更新必要**: CLAUDE.md の `{layer: layer1, interface: leaf1-swp51}` 等を全て `{interface: leaf1-swp51}` に書き換える
- **ID 衝突時の被害拡大**: グローバル一意性が破れると `attaches_to` の解決先が一意に決まらない。ADR-0002 のバリデーター強化に依存
- **multi-homing 先送り**: Phase 1 で dvSwitch の複数 vmnic 表現が制限される

### 影響を受けるコンポーネント

- **スキーマ** (`schema/layer1.py`): `AttachesTo` Union の再定義。`layer` フィールドの廃止。`L1Node.attaches_to: str | AttachesToNode`、`L1Interface.attaches_to: AttachesToInterface | None`
- **パーサー** (`parser.py`): 正規化フェーズで文字列 → `{node: str}` に変換するロジックを追加
- **バリデーター** (`validator.py`): D6 表の各チェック実装。グローバル一意 ID テーブルを参照解決に使用
- **エクスポーター** (`exporter/yaml.py`): 常にオブジェクト形式で出力 (糖衣構文を吐かない)
- **エクスポーター** (`exporter/rfc8345.py`): D7 のロジックで層復元
- **サンプル**: `tests/fixtures/valid_l1_simple.yaml` および CLAUDE.md 内サンプルから `layer:` を削除
- **文書**: CLAUDE.md の「重要な設計決定 1」テーブルと YAML サンプルを本 ADR の決定に揃えて改訂

## Alternatives Considered

### 代替案 A: RFC 8345 の 3 フィールド分割をそのまま採用

- **却下理由**: DSL としての記述量が増加。原案の MLNDL が単一フィールドで表現していた継承の意義が薄れる。RFC 8345 との変換はエクスポーターで担保すれば十分

### 代替案 B: `layer` フィールドを残す

`attaches_to: {layer: layer1, interface: leaf1-swp51}` を正規形にする。

- **却下理由**:
  - **冗長**: ID がグローバル一意なら `layer` は逆引きできる冗長情報
  - **整合性リスク**: `layer: layer2` と書いたが実際の ID が L1 のものだった場合、矛盾検出ロジックが追加で必要
  - **前方互換性論の棄却**: ID 空間分割への退行は `ndl_version: "2.0"` でのバージョン bump が正しい手法。`layer` を予約する必要はない
  - ADR-0002 (Pass C) のグローバル一意性と直接矛盾する

### 代替案 C: フィールド名を `parent` / `bound_to` 等に変更

- **不採用理由**: 本 ADR の責務は「使い分け基準」の確定。命名の再評価は将来の別 ADR に積む。現時点では `attaches_to` を維持することで、Pass C 他 ADR の確定を阻害しない

### 代替案 D: ノード参照と IF/リンク参照で別フィールドにする

(`attaches_to_node` + `attaches_to_endpoint`)

- **却下理由**: 「supporting 関係」という 1 軸を 2 フィールドに分けると論文以来の MLNDL の設計思想から逸れる。タグ付き Union (D2) で型安全性と簡潔さを両立できるため不要

### 代替案 E: Phase 1 から `list[AttachesTo]` を受け入れる (multi-homing 前倒し)

- **却下理由**: Phase 1 は最小成果物の確定段階。multi-homing が真に必要なユースケース (dvSwitch の vmnic 多重 attach) は `managed_hosts` で代替可能。配列拡張は後方互換で導入可能なので前倒しのコストメリットが薄い

## Pass A との差分

| 項目 | Pass A (推定) | Pass C | 差分の理由 |
|------|-------------|--------|----------|
| `layer` フィールド | `{layer: layer1, interface: ...}` を要求 | **廃止**。`{interface: ...}` のみ | ADR-0002 (Pass C) でグローバル一意 ID を確定したため冗長 |
| Union 判別方式 | shape-based discriminator | **タグ付き Union** (キー名 `node`/`interface`/`link` で判別) | pydantic v2 の型安全性向上 |
| 文字列糖衣の意味 | 暗黙のノード参照 | **ノード参照に限定する明文ルール**。生成系はオブジェクト形式必須 | ID 種別が文字列だけでは判別不能 |
| multi-homing | 曖昧 | **Phase 1 はスカラーのみと明示**、回避策を文書化 | スコープ明確化 |
| 自己参照 / 同層 / 上位層 | 「自己参照は不正」のみ | **D5/D6 で全ケースの severity を明文化** | spec-architect 指摘への対応 |
| severity 定義の帰属 | アドホック | **ADR-0002 D8 を参照** (本 ADR は使わない) | 横断的統一化 |

**独立に同じ結論に到達した点** (Pass A とも一致):
- `attaches_to` という統一フィールド名の維持
- supporting 関係を 3 フィールドに分割しない方針
- 自己参照は error 扱い

## ADR-0005 との関係

ADR-0005「mlndl の表現スコープ定義」(Pass C, 2026-05-29) により、`{interface: X}` の X が指せる層が D2-3 で明文化された:

| X が指す層 | ID 例 | 用途 |
|-----------|-------|------|
| L1 物理 IF | `leaf1-swp51` | routed 物理 IF のL3 終端 (D2-2 ケース A) |
| L2 VLAN (SVI 経由) | `vlan-100` | SVI の L3 終端 (D2-2 ケース B) |
| L2 サブインターフェース (Phase 2) | `leaf1-swp1-100` | L3 over sub-IF (D2-2 ケース C) |

本 ADR の D2 タグ付き Union はこれらすべてに対応する (`layer` フィールドなしで ID のグローバル一意性により層が決定)。

また ADR-0005 D2-4 は本 ADR D1 の「`attaches_to` 単一手段方針」を上位 ADR として再確認している。

## References

- `CLAUDE.md` — 「重要な設計決定 1. `attaches_to`」(本 ADR の決定に従って改訂が必要)
- `docs/decisions/evaluations/round1-evaluation.md` — Pass B 横断評価
- ADR-0002 (Pass C) — ID グローバル一意性の根拠。`layer` フィールド廃止の前提条件。severity D8 の定義元
- ADR-0005 (Pass C) — mlndl の三側面スコープ定義。`{interface: X}` の X が指せる層の詳細 (D2-3)、`attaches_to` 単一手段方針の再確認 (D2-4)
- RFC 8345 — Supporting node / TP / link の元概念
- MLNDL 原案 (NAIST, 2011) — MLNDL における「単一の attach 関係」設計思想の源流

# ADR-0013 設計比較 YAML — VLAN trunk_ports / access_ports から LAG を指す

`layer2.vlans[].trunk_ports` / `access_ports` の `interface` は現在 L1 IF id のみ。
LAG (`layer1.lag[]`、`type: lacp` は `node` 単数 / `type: mlag` は `nodes: [a,b]` 複数) を直接指せない。
本ディレクトリは 3 案 × 3 シナリオ + ありがちなミスの試し書き。**ADR-0013 確定前の仮構文**であり、
`tests/fixtures/` の対象外。

## 3 案

| 案 | `interface:` が指すもの | `node:` の扱い | MLAG |
|---|---|---|---|
| A | L1 IF id **または** LAG id (同一フィールド) | 必須 | 両ノード分 **2 エントリ** |
| B | L1 IF id **または** LAG id (同一フィールド) | LAG を指すときは **省略可**(導出) | 1 エントリ |
| C | `interface:` は L1 IF id のみ。新キー `lag:` を追加 (排他) | LAG のときも省略可 | 1 エントリ |

## 3 シナリオ

| ファイル | 内容 |
|---|---|
| `C1_plan{A,B,C}_mlag_server1.yaml` | `valid_full_dc.yaml` の MLAG trunk を LAG 参照に書き換え |
| `C2_plan{A,B,C}_lacp_trunk_server_access.yaml` | ToR→Server2 LACP を trunk、サーバー bond を access に (サーバー bond 載せる載せない判断つき) |
| `C3_plan{A,B,C}_peerlink_trunk.yaml` | MLAG peer-link bond を trunk に載せる (VLAN 100 を peer-link に流す) |

## ありがちなミス (案 B を前提)

| ファイル | ミスの種類 | 期待する検出 |
|---|---|---|
| `C4_mistake_lag_and_members.yaml` | LAG id と、その members (L1 IF) の両方を書く | error (二重表現) |
| `C4_mistake_mlag_one_node_only.yaml` | MLAG を 1 エントリで書き、`node` を片方だけ明示 | 案 A では error / 案 B/C では node 導出で救えるかの判断材料 |
| `C4_mistake_lag_wrong_node.yaml` | 別ノードの LAG id を `node` と組み合わせる | error (`node` が LAG の `node`/`nodes` に含まれない) |

## 書き手観点のサマリ

本 README 末尾の `## 推奨` を参照。各ファイル先頭コメントに案別の書きやすさを記載。

## 推奨

**案 B** を推す。理由:

1. **二重表現が減る** — MLAG は 1 エントリで済み、`node` は LAG から導出できる (members を書けば分かる情報)。
   ADR-0012 D2 で採った「親から導出できる情報は書かない」原則に揃う。
2. **構文の局所拡張で済む** — `interface:` の値域を広げるだけ。VLAN スキーマに新しいキーを増やさない。
   `PortRef` の形は保たれ、既存の `{node, interface}` 書き方は後方互換。
3. **MLAG peer-link のような 2 ノード共有物を自然に書ける** — ノードを 2 回書く必要がない。
4. **ミスは検出可能** — 「別ノードの LAG を指す」「LAG id と members を両方書く」は参照整合性で捕れる。

案 A の欠点: MLAG を 2 エントリ書くのは `lag` エンティティで既に `nodes: [leaf1, leaf2]` と宣言した事実と
重複する。VLAN 側で `node: leaf1` / `node: leaf2` を書き分ける意味がない。
案 C の欠点: フィールドが 2 本に増え、`interface` と `lag` の排他を人間が覚える必要がある。
`PortRef` を Discriminated Union に近づけることになるが、`type:` キーがないので区別が暗黙的。

**ただし** `interface:` フィールド名が「L1 IF (physical port) を指す」という素朴な読者の期待から
ずれる懸念がある。ADR-0012 では `attaches_to: {interface: <L1 IF または LAG>}` と同じ合流を既に採っており、
その意味では一貫する。命名の最終判断は `mlndl-linguist` に委ねる。

## 技術的疑問 (network-tech-reviewer へ)

- サーバー側 bond (`lag-server2-bond0`) を VLAN の `access_ports` に書くのは意味的に自然か。
  サーバーは「スイッチングしていない」ので VLAN メンバーシップの概念が宿主側 (ToR) にしか
  存在しないケースが多い。C2 では「書かない」版を採用した。
- MLAG peer-link を VLAN trunk に載せる書き方は実機 (Cumulus/EOS) で明示設定するが、
  論理モデルとしては「MLAG によって自動的に VLAN が共有される」とも読める。
  mlndl は書くべきか書かないべきか。C3 では「書く」版で試した。

## 採否 (2026-10-11、[ADR-0013](../../drafts/0013-vlan-ports-on-lag.md))

**案 B を拡げた形で採用**。`node` は LAG のときだけでなく常に省略可とし (ユーザー判断)、MLAG に `node` を書くのは error にした。
案 A・案 C は却下。上の「技術的疑問」は ADR-0013 D6 で扱った (peer-link もサーバー側 bond も、書いても書かなくてもよい)。

実装後の `python -m mlndl validate` の結果:

| ファイル | 結果 |
|---|---|
| `C1_planB` / `C2_planA` / `C2_planB` / `C3_planA` / `C3_planB` | 通る |
| `C1_planA` (MLAG を 2 エントリ) | error 3 件 (MLAG に `node` × 2、同じ端点の重複) |
| `C1_planC` / `C2_planC` / `C3_planC` (`lag:` キー) | error (`lag` は存在しないキー) |
| `C4_mistake_lag_and_members` | error (LAG とメンバーの併記) |
| `C4_mistake_lag_wrong_node` | error (LAG のノードと `node` の食い違い) |
| `C4_mistake_mlag_one_node_only` | error (MLAG に `node`) |

`C2_planA` と `C3_*` は LACP の LAG に `node` を書いているだけなので、採用案でも通る。

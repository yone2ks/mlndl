# mlndl role 語彙リファレンス

> **ステータス: Informative (参考情報)**
>
> このドキュメントは ADR-0003 (Pass C2) D6 に基づく informative リファレンスです。
> mlndl コアのバリデーターはこのドキュメントを参照せず、`role` 値域チェックを行いません。
> ndl-viz の**既定スタイル適用**および ndl-viz / ValidationPlugin の語彙チェックは、
> このドキュメントの推奨語彙を前提とします。

---

## 推奨語彙 (CANONICAL_ROLES)

以下の 9 語が推奨値として定義されています。`src/mlndl/constants.py` の `CANONICAL_ROLES` と同一の語彙です。

| role | 意味 | 想定 implementation | 備考 |
|------|------|---------------------|------|
| `spine` | Clos ファブリックのスパイン層。スパイン同士の水平接続を持たない | vm / physical / container | Spine-Leaf DC ファブリックの上位層 |
| `leaf` | Clos ファブリックのリーフ層。サーバー・ストレージへのアクセス段 | vm / physical / container | Spine-Leaf DC ファブリックの下位層 |
| `core` | エンタープライズ/SP コアレイヤ。高速転送専用 | physical | エンタープライズ 3-Tier / SP コアバックボーン |
| `border` | AS 境界ルーターまたは DC エッジ。外部 BGP を終端 | physical / vm | ASBR / DC Border-Leaf 兼用 |
| `server` | エンドホスト。アプリケーション・サービスを稼働させる | physical / vm / container | ベアメタル・仮想マシン・コンテナノード |
| `firewall` | L2〜L7 のトラフィック検査・制御デバイス | physical / vm | NGFW・L4 ACL デバイス・透過型 FW を含む |
| `load-balancer` | L3〜L7 の負荷分散デバイス | physical / vm / container | F5 / Citrix / NGINX / ECMP ルーター |
| `hypervisor` | Type-1 / Type-2 ハイパーバイザを提供するホスト | physical / vm (ネステッド) | ⚠️ `implementation: container` との組み合わせは **normative error** (ADR-0004 D-1) |
| `management` | アウトオブバンド管理ネットワーク専用デバイス | physical / vm | Jump host / Bastion / OOB スイッチ |

---

## 慣習表記

- **文字セット**: 小文字英数字とハイフンのみ (`^[a-z][a-z0-9-]*$` に準拠)
- **ハイフン区切り**: 複合語はハイフンで接続 — 例: `load-balancer`、`route-reflector`
- **アンダースコア不使用**: `load_balancer` ではなく `load-balancer`

---

## ndl-viz スタイル適用ポリシー

| 状況 | ndl-viz の動作 |
|------|---------------|
| role が上記 9 語に一致 | 対応する既定スタイル (アイコン・色・配置) を適用 |
| role が 9 語以外 (例: `tap-aggregator`) | フォールバックスタイル (グレーノード) を適用。警告ログを記録 |
| role が未設定 (`null`) | フォールバックスタイルを適用。警告は出力しない |

---

## NetBox DeviceRole slug 対応表

NetBox から mlndl YAML に変換する際のアダプター参照表 (informative)。

| NetBox DeviceRole slug (慣用例) | 推奨 mlndl role | 備考 |
|-------------------------------|----------------|------|
| `spine`, `spine-switch` | `spine` | そのまま利用 |
| `leaf`, `leaf-switch`, `top-of-rack`, `tor` | `leaf` | ToR は位置概念であり論理 role 軸では `leaf` と同義 |
| `core`, `core-router` | `core` | |
| `border`, `border-router`, `asbr`, `border-leaf` | `border` | |
| `server`, `bare-metal` | `server` | |
| `firewall`, `ngfw`, `fw` | `firewall` | |
| `load-balancer`, `loadbalancer`, `lb` | `load-balancer` | |
| `hypervisor`, `esxi-host`, `kvm-host` | `hypervisor` | |
| `management`, `mgmt`, `oob` | `management` | |
| その他 / 未知 | そのまま転写 (warning 出力を推奨) | アダプターが `warning` を記録し mlndl role に渡す |

---

## 推奨しない語彙

以下は **mlndl L1 スコープには属さない** ため推奨語彙に含みません:

| 語彙 | 理由 | 代替表現 |
|------|------|---------|
| `vswitch`, `dvswitch` | ソフトウェア機能であり L1 物理「箱」ではない | Phase 2 の `layer2.bridges` 等で設計予定 |
| `eor` (End of Row) | 物理配置概念であり論理 role 軸と直交 | `leaf` または `core` で表現 |
| `router` | 機能ではなく実装タイプ。`border`/`core` 等で役割を示すほうが明確 | — |

---

## informative 慣用語彙: エンタープライズ 3-Tier キャンパス

DC Clos ファブリック (spine/leaf) とは別に、エンタープライズ キャンパスでは
**Core / Distribution / Access** の 3 階層モデルが Cisco 由来で広く使われます。
これらは CANONICAL_ROLES には含めません (ADR-0003 C2 のオープン語彙方針を維持) が、
ndl-viz は既定スタイルを用意しており、慣用語として推奨します。

| 語彙 | 階層 | 役割 | 備考 |
|------|------|------|------|
| `core` | 最上位 | バックボーン / L3 終端 | CANONICAL にも含まれる |
| `distribution` | 中間 | 集約 / L2-L3 境界 / FHRP (HSRP/VRRP) 終端 | — |
| `access` | エッジ | ホスト収容 | — |

> **注意 (用語の揺れ)**: ベンダーにより中間層を `aggregation` と呼ぶ場合があります
> (Arista/Juniper 等)。`aggregation` は「リンク集約 (LAG)」「経路集約 (route aggregation)」
> とも衝突しうるため、3-Tier 文脈では **`distribution` を推奨**します。
> また Cisco 3-Tier の `distribution` は L2/L3 境界の集約層であり、ホスト収容は `access`
> です。中間層を `distribution`、ホスト収容層を `access` と命名してください。

---

## 将来の拡張

`role` は open-form (ADR-0003 D1) のため、上記リストにない語彙を使っても mlndl コアは error を出しません。

新語彙を mlndl エコシステム全体で共有する場合は、このドキュメントへの Pull Request を送ってください。mlndl の ADR は動かしません。

---

*参照: [ADR-0003](decisions/0003-role-vocabulary.md) (Pass C2) — D1・D4・D6*

# ADR-0017 Pass C 試し書き

Pass B 評価メモ (`../evaluation.md`) の「残る論点 (Pass C 向け)」と「Pass B のあとに分かったこと」で挙がった
論点を YAML で確かめる試し書き。Pass A のドラフト (`drafts/0017-sites-and-wan.md`) は Pass C の原則に従って参照していない。

## ファイル

| ID | 目的 | 期待される validator 出力 |
|---|---|---|
| `P1_elan_ospf_3sites.yaml` | 3 拠点以上の広域イーサ (E-LAN) で拠点のルーターどうしが OSPF | **OK (errors 0)** |
| `P2a_ebgp_via_box_outside.yaml` | 広域イーサをはさむ 2 拠点 eBGP。相手は address + local_as | **OK (errors 0)** |
| `P2b_ebgp_via_box_both_inside.yaml` | 同上を両端 node で書いた invalid 版 | **ERROR (transport_mismatch)** |
| `P3_lines_vs_boxes_mixed.yaml` | ダークファイバ・DWDM・L2 専用線 (線) とモバイル閉域網 (箱) の混在 | **OK (errors 0)** |
| `P4a_site_value_short.yaml` | `labels.site: tokyo` 形式 | **OK (errors 0)** |
| `P4b_site_value_prefixed.yaml` | `labels.site: site-tokyo` 形式 | **OK (errors 0)** |

## 検証コマンド

```sh
cd mlndl
for f in docs/decisions/evaluations/adr0017/passc/P*.yaml; do
  echo "── $f ──"
  python -m mlndl validate "$f"
done
```

## 検証結果

**注記**: 試し書き担当のセッションでは `python -m mlndl validate` を実行できず、下の各節はコードを読んで書いた予想である。
2026-11-03 に統合者が 6 本を実行し、すべて予想どおりだった (P2b だけ error 1 件、ほかは errors 0)。

### P1 (E-LAN + OSPF 3 拠点)

**予想**: `OK — no validation errors`

- OSPF の隣接関係は `bgp_session_views` の `transport_mismatch` 検査の対象外
  (validator.py L791 以降は `BgpSession` だけを集める。L278 の `isinstance(session, BgpSession)`)。
- したがって 3 本の OSPF 隣接 (別々のアクセス回線上の L3 IF どうし) は通る。
- `one_end_inside()` は BGP だけの検査、OSPF はそもそも OutsideEndpoint がない。
- 評価メモ「Pass B のあとに分かったこと」の「OSPF / IS-IS は箱をはさんでも通る」の裏付け。

### P2a (eBGP via 箱、相手を外として)

**予想**: `OK — no validation errors`

- `from` が inside、`to` が outside。両端外 (`one_end_inside`) ではない。
- `_transport` は両端が inside でないと走らない (derive.py L292)。transport_mismatch 検査なし。
- S6a と同じ結論 (評価メモ「訂正」で確認済み: 逆向きを書いても validator は通るが
  1 セッションを 2 エントリに書くので ADR-0010 に反する → 片側からしか書けない)。

### P2b (eBGP via 箱、両端 node)

**予想**:

```
ERROR  control_plane.routing_neighbors[0]: 両端の update_source
  ('tokyo-rtr-ge0-l3' と 'osaka-rtr-ge0-l3') が同じリンク / LAG / VLAN の上に
  ありません。直結のインターフェースどうしで張るなら、同じリンクの両端を指して
  ください (ADR-0010 D7)
```

- `_l3_basis` は tokyo-rtr-ge0-l3 → `("l1", "tokyo-rtr-ge0", None)`、osaka-rtr-ge0-l3 → `("l1", "osaka-rtr-ge0", None)`。
- `_transport` が別の L1 IF と判定して `transport_mismatch = True`。
- validator.py L808-L813 でメッセージが出る。
- これが「次の ADR で扱う」とされた D5-2 (d) の実例。

### P3 (線と箱の混在)

**予想**: `OK — no validation errors`

- 箱 (net-docomo-gcv) は普通の L1 ノード。L3 IF を持たないことは言語の規約で、validator は検査しない
  (評価メモ「一致した点」より)。
- リンクはすべて L1 IF の id を endpoints に書くだけなので参照整合性 OK。
- 線で書いたリンク (ダークファイバ / DWDM / L2 専用線) の `description` は長文を含むが、`description` は
  自由文字列。構文の制約はない。

### P4a / P4b (labels.site の値の書き方)

**予想**: 両方とも `OK — no validation errors`

- `labels` の値は str であれば自由 (ADR-0009 D3)。
- キー `site` は ADR-0002 D1 の ID 正規表現 (`^[a-z][a-z0-9]*(-[a-z0-9]+)*$`) に適合するので warning なし。
- 値の書き方 (`tokyo` と `site-tokyo`) は validator の判定が同じ。差は ndl-viz の見え方だけ。

## Pass C で確定したい論点 (試し書きから見えた)

### 1. 広域イーサをはさむ両端 node の BGP (P2b) を error のままでよいか

`transport_mismatch` のメッセージは「直結のインターフェースどうしで張るなら、同じリンクの両端を指してください」
と言う。箱をはさむ構成の書き手にとっては、意味が通らない (直結ではない)。

- **Pass C で ADR-0017 に書くべきこと**:
  - 当面 (別 ADR 待ち) は P2a の書き方で回避する、と明記する。
  - validator のエラーメッセージを「箱をはさむセッションは次の ADR で扱う。
    暫定は address + local_as 形式で」と誘導する文言に変える案を次 ADR の TODO に。

### 2. E-LAN の OSPF (P1) を「書けてしまう」ことを ADR で言及するか

P1 は 3 本の P2P OSPF 隣接でフルメッシュを表した。実機の OSPF では multi-access network type (broadcast / NBMA)
と DR 選出が走るが、mlndl にはその概念がない。

- **技術的に不正確になりうる構成**: フルメッシュ 3 本と DR/BDR 構成は OSPF の挙動が違う (SPF コスト・LSA 種類)。
- **Pass C で ADR-0017 に書くべきこと**:
  - 「3 拠点以上の広域イーサでの OSPF は 1 セグメントを複数の P2P 隣接として記述する。
    DR/BDR・network type は構文に出さない (ADR-0005 D4 補則 問い 4)」を明記。
  - ネットワーク担当のレビューで「代表 1 本だけでよいか」の判断を仰ぎたい。

### 3. 線か箱かの判定基準の書き方 (P3)

評価メモの判定基準 (「契約が 2 点間の回線か、事業者網への接続か」) は、迷いやすい DWDM / L2 専用線 / ダークファイバ
でも機械的に効く。

- **Pass C で ADR-0017 D3 に書くべきこと**: P3 で挙げた「ダークファイバ / DWDM / L2 専用線 → 線」の判断を
  表の 1 行に足す。既にある「広域イーサ 2 拠点 → 箱」との対比で読める。
- **残る疑問**: SD-WAN と「サービスとしてのダークファイバ」の線引き (評価メモの表に SD-WAN は入っている)。

### 4. labels.site の値の書き方 (P4)

- **現状の表記揺れ**: `label-vocabulary.md` が `site-tokyo`、`examples/wan-sites.yaml` と `tests/fixtures/valid_multisite_wan.yaml`
  と 既存の S1〜S6b が `tokyo`。
- **ndl-viz での見え方**: `site-tokyo` だと枠のタイトルに「site-」が付いて冗長 ("site site-tokyo" のように読める)。
- **提案**: ADR-0017 で「値は拠点の固有名詞 (`tokyo`、`dc1` 等) にする」を規約として確定。
  `label-vocabulary.md` の例を `tokyo` に揃える加筆を Consequences に書く。
- **他軸との混同**: キー名 (site / az / region) で軸を区別する前提 (ADR-0009 D3)。値だけで識別するニーズは出ていない。

## 他担当と割れそうな点

- **ネットワーク担当**: P1 の「フルメッシュ 3 本で E-LAN の OSPF を表す」の是非。DR/BDR を書けないことを ADR で
  どこまで注意書きにすべきか (「書くな」まで言うか、「書けないが実機では DR 選出があることを前提に」の注で済ますか)。
- **DSL 担当**: P2a で「自分の機器を外として書く」ことが残る違和感。P4 の値の形 (`tokyo` vs `site-tokyo`) は
  注釈側の open-form とどう整合するか (構文の規約として縛ると注釈側構成子の原則に反するのでは)。
- **言語担当**: P4 で `labels.site` の値を規約で揃えるとき、他の labels のキーの値にも波及するか。
  個別に決めるのか、全体の規約として「labels の値は固有名詞 1 語」を書くのか。
- **仕様担当 (ADR 判断)**: P2b の挙動を error のまま残して ADR-0017 を Accept できるか、
  それとも error メッセージの改善を ADR-0017 のタスクに含めるか。

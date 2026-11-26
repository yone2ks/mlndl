# ADR-0029 Pass B のまとめ

5 つのエージェントの Pass B (横断の評価) と試し書き (b1〜b4) を並べ、一致した所・分かれた所・ユーザーに決めてもらう所を整理する。各報告は同じディレクトリの `b-*.md`。

## 一致した所

1. **Pass A の推奨モデルを採る**。ドメイン = 中でフルメッシュにトンネルを張る VTEP の集合。1 つの VTEP は 1 つのドメイン (多対多は却下)。DCI も 1 つのドメイン。BGW は 2 つのドメインに VTEP を 1 つずつ持つ (ADR-0014 D6 の書き方のまま、各エントリにドメインを足す)。トンネルの対は「同じ L2VNI に参加し、同じドメインに属する VTEP どうし」
2. **名前は `overlay_domains`** (5 つとも第一候補か同意)。次点 `vxlan_domains`。`fabrics` は DCI に合わない。プレフィックスは `od-`。日本語は「オーバーレイのドメイン」
3. **ドメインは任意**。書かなければ全 VTEP が暗黙の 1 つのドメイン。今の 5 本の fixture は書き換えなしで valid。stretched fabric は書かない形が自然 (b4)
4. **L2VNI のスキーマは変えない**。参加機器の導き方 (ADR-0026 D4) も変えない。トンネルの対は別の導出 (`l2vni_tunnel_pairs`)
5. **L3VNI には `vteps` を足さない**。L3VNI のドメインは VRF から導く
6. **核心の検査**: L2VNI の VTEP が 2 つ以上のドメインにまたがるのに、2 つのドメインに VTEP を持つ機器 (BGW) が 1 台もない → error
7. **BGW の warning (ADR-0026 D5 の 10) を抑える**: 2 つのドメインに VTEP を持つ機器なら出さない (試し書き a1 で 4 つ出ることを確かめた)
8. **範囲外 (先送り)**: VNI stitching、RT の付け替え、BUM の方式をドメインごとに変えること、L3VNI の明示の `vteps`
9. **方式名を構文に入れない**。`anycast` / `multisite` / `stretched` をドメインのフィールドにしない
10. **エクスポーター**: VTEP に `overlay_domain`、トンネルは同じドメインの VTEP の対で辺を描く (any-to-any の誤読を防ぐ)。ndl-viz はドメインを枠で描ける

## 分かれた所

### 1. 書く場所: A1 (VTEP の `overlay_domain:`) か A2 (ドメインの `members`)

- **A1**: dsl-designer、spec-architect、linguist、example-author
  - 1 つの VTEP は 1 つのドメインが型で決まる (A2 は検査が要る)
  - 同じ情報を 2 か所に書かない (A2 は `members` と L2VNI の `vteps` に VTEP が二重に出る)
  - 記述量が少ない (b1 と b2 で確かめた)。書かないときとの境界が自然
  - `lags[].node` と同じ「子が親を単数で指す」形 (ADR-0023)
- **A2**: network-tech-reviewer
  - ドメインの中身が 1 か所で見渡せる。`bridges` の `ports`・ES の `members` と同じ流儀
  - 「A1 はドメインに属性を付けにくい」という理由は当たらない (A1 もドメインの一覧を持つ)

**推奨: A1**。

### 2. 1 本のループバックで 2 つのドメインを終端する構成

network-tech-reviewer の指摘。NX-OS は 2 本のループバック (サイト内と Multi-Site の VIP) が普通だが、Arista の一部・ハイパーバイザの VTEP などでは 1 本のループバックで両方を終端する。このモデルでは、同じ L3 IF を 2 つの VTEP (2 つのドメイン) に書くことになり、今の「同じ L3 IF を 2 つの VTEP に書かない」(ADR-0014 の検査、error) に当たる。

- (a) 違うドメインの VTEP なら、同じ L3 IF を 2 つに書いてよい (warning か検査しない)
- (b) 今回は扱わない (2 本のループバックの構成だけ。1 本の構成は先送り)

### 3. `role: border-gateway`

- linguist・spec-architect: 推奨の 9 語は変えず、role-vocabulary.md の informative の節に足す (validator は読まない)
- network-tech-reviewer: 足さない (構造から導ける)

### 4. hub-and-spoke の DCI

- spec-architect: hub の BGW がスポークごとに VTEP を持てば、複数の DCI のドメインで書ける
- network-tech-reviewer・example-author: 「中でフルメッシュ」の定義から外れる。範囲外と明記する

実際の hub-and-spoke (route server が hub) は制御プレーンだけが hub で、データプレーンは BGW のフルメッシュのことが多い。データプレーンも階層になる構成はまれ。**推奨: 範囲外と明記し、先送り**。

### 5. 検査の細部 (Pass C で決める)

| 検査 | 意見 |
|---|---|
| VTEP が 0 のドメイン | error (spec) / warning (dsl) |
| VTEP が 1 のドメイン | warning (spec・dsl) / 出さないか info (network。stretched で偽の警告) |
| ドメインを書いた VTEP と書かない VTEP の混在 | error (dsl) |
| ドメインが 1 つだけ | warning (dsl) |
| サイト間の EVPN セッションとドメインの境界 | しない (dsl。ADR-0010 で制御プレーンとデータプレーンを独立に) / info (spec) / warning (network) |

### 6. L3VNI のドメインの導き方 (Pass C で決める)

- dsl-designer・network-tech-reviewer・example-author: L3VNI の VRF の L3 IF を持つ機器が終端する VTEP の、同じドメインの対
- spec-architect: 同じ VRF の L2VNI のドメインの和集合

BGW は普通 VRF の L3 IF を持たない (L3VNI の SVI を持つ構成もある) ので、前者だと BGW が L3VNI に入らないことがある。Pass C で確かめる。

## 見本 (Pass C の後に作る)

`tests/fixtures/valid_evpn_multisite.yaml` (a1 がもと)。2 サイト、各サイトに spine 2・leaf 2・anycast BGW 2・サーバー 1。L2VNI 1 + L3VNI 1。DCI は直結。network-tech-reviewer の指摘を入れる: BGW のループバックを DCI の underlay に広告する前提をコメントに、tenant-a の BGP インスタンスを書く、MTU は MLNDL の対象外だが実機では 1600 以上とコメントに。

## 別に見つかった問題 (この ADR と別に直す)

- BGP のインスタンスに `vrf: vrf-default` と書くと「vrf-default のセッションが l2vpn_evpn を運んでいます。これらの経路は default VRF のセッションで…」と自己矛盾に見える warning が出る
- fixture の多くが L3 IF に `vrf: vrf-default` と書いている (書き方の推奨は「default VRF なら書かない」)
- labels のキーに下線が書けないこと (`fabric_role`) が分かりにくい

## ユーザーの判断 (2026-11-26)

| 論点 | 判断 |
|---|---|
| 書く場所 | A1 (VTEP に `overlay_domain:`) |
| 名前 | `overlay_domains` / `overlay_domain:`、プレフィックス `od-` |
| 1 本のループバックで 2 つのドメインを終端する構成 | 今回は扱わない (先送り。今の「同じ L3 IF を 2 つの VTEP に書かない」検査はそのまま) |
| `role: border-gateway` | role-vocabulary.md の informative の節に足す (推奨の 9 語は変えない。validator は読まない) |

hub-and-spoke の DCI は推奨どおり範囲外とし、先送りに記録する。検査の細部 (分かれた所の 5) と L3VNI の導き方 (6) は Pass C で決める。

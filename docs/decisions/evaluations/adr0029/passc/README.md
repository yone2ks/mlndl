# ADR-0029 Pass C — 試し書き

Pass A の案 (`drafts/0029-*`) は見ず、`../passb/summary.md` と末尾のユーザーの判断、
試し書き `a1-current-syntax.yaml` / `b1-domain-on-vtep.yaml` / `b4-stretched.yaml`
だけを入力に、ゼロから書いた。

## 前提 (Pass B 判断から蒸し返さない)

- 書き方は A1: `layer2.overlay_domains: [{id, name?, description?}]` と VTEP の `overlay_domain: <id>`
- 名前は `overlay_domains` / `overlay_domain:`、プレフィックス `od-`
- 1 つの VTEP は 1 つのドメイン。DCI も 1 つのドメイン。BGW は 2 つのドメインに
  VTEP を 1 つずつ持つ
- `overlay_domain` は任意。書かなければ全 VTEP が 1 つの暗黙のドメイン
- L2VNI のスキーマは変えない (参加ドメインは参照先の VTEP から導く)
- 1 本のループバックで 2 ドメインを終端する構成は先送り (今回は扱わない)
- `role: border-gateway` は informative (role-vocabulary.md に足す。validator は読まない)

## ファイル一覧

| ファイル | 想定結果 | 確かめること |
|---|---|---|
| [p1-evpn-multisite.yaml](p1-evpn-multisite.yaml) | valid | 2 サイトの EVPN Multi-Site の見本。各サイト spine 2・leaf 2・anycast BGW 2・サーバー 1、L2VNI 1 (vlan-100) + L3VNI 1 (vrf-tenant-a、Symmetric IRB)、DCI 直結。`od-site-a` / `od-site-b` / `od-dci` の 3 つのドメイン。BGW は od-site-* と od-dci の両方に VTEP を 1 つずつ持つ (lo1 = site VIP、lo2 = Multi-Site VIP)。tenant-a の BGP インスタンスも書く。`vrf-default` は書かない (ADR-0028 D4)。のちに `tests/fixtures/valid_evpn_multisite.yaml` になる候補 |
| [p2a-undefined-domain.yaml](p2a-undefined-domain.yaml) | error (確定) | VTEP の `overlay_domain` が overlay_domains にない id を指す。ADR-0015 の `Ref` の汎用の検査が捕まえる (新しい検査ロジックは要らない) |
| [p2b-no-bgw-across-domains.yaml](p2b-no-bgw-across-domains.yaml) | error (確定) | L2VNI の参加 VTEP が 2 つ以上のドメインに属するのに、両ドメインに VTEP を持つ機器 (BGW) が 1 台もない。Pass B summary「一致した所」6 の核心の検査 |
| [p2c-partial-domain.yaml](p2c-partial-domain.yaml) | error (推奨) | 一部の VTEP だけ `overlay_domain` を書いた。暗黙のドメインと明示のドメインの境界が曖昧になる混乱を早期に止める (Pass B summary「検査の細部」3 — dsl-designer 案) |
| [p2d-vtep-cardinality.yaml](p2d-vtep-cardinality.yaml) | warning (推奨、未定) | VTEP 0 のドメイン (未使用) と VTEP 1 のドメイン (対がない)。どちらも warning を推奨。Pass B summary「検査の細部」1・2 の結論は Pass C で決める |
| [p3-no-domain.yaml](p3-no-domain.yaml) | valid (確定) | `overlay_domains` を書かず、VTEP に `overlay_domain` も書かない。「暗黙の 1 ドメイン = 従来どおりフルメッシュ」。ADR-0027 の加算的変更の約束どおり、既存の fixture (valid_full_dc.yaml など) はそのまま通る |

## 読み方

すべての YAML の先頭のコメントに、次を書いた:

- 何を確かめるためのファイルか
- 期待する結果 (valid / error / warning / 未定)
- 構成と前提
- 判断の分かれる所は「未定」と記し、ADR 本文の判断を待つ

## `overlay_domain` を消せば今の mlndl で valid になるか

**なる (そう書いた)**。p1 と p3 は、`overlay_domains` の区画と各 VTEP の
`overlay_domain:` を消せば今の mlndl で valid になるつもりで書いた。

p1 を今の mlndl で確かめる方法:

1. `layer2.overlay_domains` を丸ごと消す
2. 各 VTEP の `overlay_domain: od-…` を消す
3. 残りはそのまま。今の validator を通る (はず)

p3 はもともと `overlay_domains` / `overlay_domain` を書いていないので、
そのまま今の mlndl に食わせられる (はず)。

p2a〜p2d は新しい検査を試すためのファイルなので、今の mlndl では
`overlay_domains` と `overlay_domain:` が未知のキーの error になる (ADR-0029 を
実装した後に初めて意味のあるメッセージになる)。

## Pass C の判断に残した点 (レポートに回す)

1. ドメインが 1 つだけの構成の扱い (warning か、出さないか)
2. VTEP 0 のドメインの扱い (error か warning か)
3. L3VNI のドメインの導き方 (Pass B summary「検査の細部」6 の 2 案)
4. 「書く場所」の予約: `overlay_domain` のキーを 1 本の loopback の構成
   (lo が 2 ドメインを終端) まで含めて拡張する余地 (Pass B 判断 2 — 今回は扱わない)

これらは p1〜p3 の書き方に影響しない (どの案でも p1 は valid、p3 は valid)。

## 統合で直したこと (2026-11-26)

- p1: BGP のエントリが 2 つ (`bgp-default` と tenant-a) あるので、`instance` のないセッション 20 本に `instance: bgp-default` を足した (ADR-0010 D3。足す前は今の validator で error)
- p1: labels の `fabric-role` を消した。BGW の目印は `role: border-gateway` だけにする (同じ情報を 2 か所に書かない)
- 確かめた結果: p1 から `overlay_domains` と `overlay_domain:` を消すと、今の validator で error なし。warning は BGW の 4 つ (ADR-0026 D5 の 10) だけで、ADR-0029 D6 で消える。p3 は今の validator で valid。p2b はドメインを消すと valid (ドメインがあって初めて error になる例)
- p2d の想定: ADR-0029 D5 で、VTEP のないドメインは warning、VTEP が 1 つのドメインは検査しないと決めた

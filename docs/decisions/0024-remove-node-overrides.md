# ADR-0024: 機器の `overrides` をなくす

- **Status**: Accepted (2026-11-09 に実装)
- **Date**: 2026-11-09
- **Deciders**: mlndl-spec-architect, mlndl-linguist, mlndl-dsl-designer, network-tech-reviewer, mlndl-example-author、ユーザー
- **Pass**: C (5 エージェントの検討を 1 回で行った。下書きはない)
- **関連**: ADR-0005 (D3-1 のスコープ表、D4 補則)、ADR-0009 (`labels`)、ADR-0011 D7 / ADR-0017 D4 (`description`)、
  ADR-0020 (同じ形でフィールドをなくした)、[ADR-0022](0022-diagram-granularity.md) (問い 5: 構成図の粒度)

## Context

`layer1.nodes[].overrides` は `dict[str, Any]` の任意のマッピングで、キーも値も自由だった。
CLAUDE.md の例は `overrides: {eve_ng: {cpu: 4}}` で、eve-lab-builder が `device_type` から引く CPU / RAM の既定値を機器ごとに上書きするためのものだった。

調べて分かったこと:

- 決めた ADR がない。ADR-0005 の L1 のスコープ表に名前があるだけだった
- 検査はない。Cytoscape のエクスポーターは出さず、ndl-viz も使わない。fixtures・examples・テストに使用例はない
- 「EVE-NG 固有の情報 (template / CPU / RAM) は mlndl に書かない」(CLAUDE.md §8) と食い違う。`overrides.eve_ng.cpu` はその情報を YAML に書く穴だった
- ADR-0022 の問い 5 「装置に設定するためだけの値は書かない」とも食い違う。CPU / RAM / イメージはラボを建てる設定の粒度である
- ADR-0022 の「悪い影響」に「テナントごとに違う anycast MAC は上位のツール (`overrides` など) で持つ」と書いてしまい、
  問い 5 で外した値の逃げ場として `overrides` を名指ししていた
- 何でも書ける欄は、1.0 のリリース後に一度使われると狭められない

試し書き ([evaluations/adr0024/](evaluations/adr0024/)) では、`overrides` に次の弱点があった:

- `eve_ng` のような名前空間の付け方に決まりがなく、ラボごとにばらつく
- `eve_ng` を `eveng` と書き違えても何も言われず、下流のツールが黙って既定値を使う
- `template` を `device_type` の対応表と `overrides` の 2 か所に書ける
- 管理 IP のように L3 IF に書くべき値まで逃がせる

下流のツールは、機器ごとの設定をもともと自分で持っている (Containerlab の `topology.yaml` の `nodes:`、Ansible の `host_vars/<id>.yaml`、
EVE-NG のラボの設定、NetBox のデバイス)。mlndl の id は ADR-0002 の文法に従う安定した参照キーなので、下流のツールはそれを引けばよい。

## Decision

### D1. `layer1.nodes[].overrides` をなくす

機器に `overrides` を書かない。1.0 のリリース前なので、猶予期間 (warning) は設けない。
書いた場合は、一般の「余分なキー」ではなく、なくした理由と移動先を示す error にする (ADR-0020 D1 と同じ)。

```
layer1.nodes の overrides はなくしました。機器ごとの CPU・RAM・イメージなどは、下流のツール (eve-lab-builder など) の設定で
機器の id を引いて書きます。人が読む補足は description に書きます (ADR-0024)
```

### D2. 下流のツールの値は、下流のツールの設定に持つ

機器ごとの CPU・RAM・イメージ・テンプレートなど、ラボや装置を建てるための値は、下流のツールが自分の設定ファイルで持ち、mlndl の機器の id で引く。

```yaml
# eve-lab-builder の設定 (mlndl の外。mlndl はこのファイルを見ない)
nodes:
  border1:
    cpu: 4
    ram: 6144
    template: cumulus-vx-5.9
```

同じ `device_type` の機器のうち 1 台だけイメージを変える場合も、下流のツールの機器ごとの上書きで扱う。
そのために `device_type` を `cumulus_linux_59` のように分けることはしない (`device_type` は機種の抽象キーのまま。CLAUDE.md §8)。
id ではなく `role` や `labels` で引くかどうかは下流のツールの設計で、mlndl は id・`role`・`labels` を出すところまでにする。

### D3. ツール向けの汎用の欄は 1.x では足さない

「どのエンティティにもツール向けのメモを書きたい」という求めには、汎用の欄で応えない。

- 人が読む補足は `description` に書く (ツールはパースしない。ADR-0011 D7 / ADR-0017 D4)
- 分類は `labels` に書く (値は参照ではない文字列。ADR-0009)
- それ以外で構成図に要るものは、ADR で決めて専用のフィールドを足す (ADR-0005 D4 補則の問い 1〜5 で判断する)

それでも汎用の欄が要るとわかったら、名前空間付きで値が文字列の形 (Kubernetes の annotations に近い `map[str, str]`) を ADR で検討する。
`dict[str, Any]` には戻さない。後から足しても既存の YAML は壊れない (加算的変更)。

### D4. ADR-0022 の記述を直す

ADR-0022 の「悪い影響」の「上位のツール (`overrides` など) で持つ」を「上位のツールの設定で機器の id を引いて持つ」に直す。

## Consequences

**良い影響:**

- 中身の決まらない欄がなくなり、CLAUDE.md §8 と ADR-0022 の問い 5 に食い違う箇所がなくなった
- 下流のツールの値が mlndl の YAML と下流のツールの設定の 2 か所に分かれない。書き違いは下流のツールが自分のスキーマで検査できる
- ツール向けの欄を将来作るとき、名前空間と値の型を決めてから作れる

**悪い影響 / トレードオフ:**

- 1 つのファイルでラボを完結させる書き方はできなくなる。機器ごとの CPU / RAM を変えるラボは、下流のツールの設定ファイルが要る
- 機器の id を変えると、下流のツールの設定も直す必要がある (id で引くため)

**影響を受けるコンポーネント:**

- スキーマ: `src/mlndl/schema/layer1.py` (`L1Node.overrides` を削り、書いたら error)
- 文書: `docs/reference/` (layer1・types・schema.json)、ADR-0005 (D3-1 の表)、ADR-0022、`CLAUDE.md`
- 下流のツール: eve-lab-builder は機器の id で引く上書きの設定を持つ (このリポジトリの外)

## Alternatives Considered

- **なくす** *(採用案)*: 5 エージェントとも推奨した
- **残して `eve_ng` だけに絞る**: mlndl が特定の下流ツールの名前を知ることになる。「mlndl は EVE-NG を知らない」という位置づけと合わない
- **`vendor_extensions` などに改名する**: 名前を変えても `dict[str, Any]` の穴は残る。`override` という名前は言語の外の既定値を前提にしていて、どの名前でもその前提は消えない (mlndl-linguist)
- **段階的に廃止する (1.x の間は warning、2.0 で削除)**: 1.0 のリリース前は破壊的な変更を許す方針 (ADR-0010 の移行の改訂) なので取らない

## References

- 試し書き: [evaluations/adr0024/](evaluations/adr0024/) (`a_with_overrides.yaml` / `b_no_overrides.yaml` / `b_eve_lab_builder_overrides.yaml`)
- Kubernetes の annotations、Terraform の provider ブロック、YANG の augment、OpenAPI の `x-` 拡張 (ツール向けの拡張欄の比較。mlndl-dsl-designer)

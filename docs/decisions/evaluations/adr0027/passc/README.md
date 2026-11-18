# ADR-0027 Pass C の試し書き

| ファイル | 内容 |
|---|---|
| p1-ndl-version-unquoted.yaml | `ndl_version` を引用符なしで書いた |
| p2-ndl-1-1-only-1-0-keys.yaml | `"1.1"` と書いたが 1.0 のキーだけを使った |
| p3-meta-tool-settings.yaml | `meta` に下流のツールの設定 (`meta.ndl-viz` など) を書いた |
| p4a-vxlans-levels-split.yaml | 名前の直しの案 a: `lags` / `vxlans` / `level_1`・`level_2`・`level_all` (推奨) |
| p4b-vnis-level-combined.yaml | 名前の直しの案 b: `lags` / `vnis` / `level_1`・`level_2`・`level_1_2` (採らない) |

検証の結果は [../evaluation.md](../evaluation.md) の「Pass C の結果」。P4 は ADR-0028 を実装するまで今の validator では通らない。

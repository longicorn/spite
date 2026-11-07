# Spite

[English Document](README.md)

Spiteは、システム開発における納期予測を確率分布に基づいて行うための実験用ツールです。

既存の納期予測や工数管理は、現場エンジニアの勘やビジネス都合の要求、あるいは過去のスループットやサイクルタイムからの計算に頼ることが多く、既存ツールもこれらの考え方に寄っています。「納期とは確率分布である」という考え方は以前から存在するものの、複雑なシステム開発の現場で具体的にどう扱うかは確立されていません。

Spiteは、開発初期から仮の確率分布を置いて3シナリオ（最善・通常・最悪）の予測を行い、完了後の実績と照らし合わせて予測手法を探求することを目的にしています。

## 使い方

現在は対数正規分布を用いた3シナリオ（最善・通常・最悪）の計算とグラフ表示に対応しており、開発中案件の予測と完了済み案件の振り返りが行えます。

詳しいオプション指定方法は `--help` を参照してください。

```bash
$ uv run spite predict --help
```

### 予測モード（開発未完了・着手前の場合）

最善・通常・最悪の各シナリオについて、P50・P80・P90の完了予測日と稼働日数を表示します。画像出力（`--output`）や画面表示（`--show`）を指定しない場合は、ターミナルにASCIIグラフを表示します。

```bash
$ uv run spite predict --distribution lognormal --start-date 2024-09-10 --deadline 2024-09-30 --output output.png
```

### 振り返りモード（開発完了済みの場合）

`--actual-end-date` を指定すると、通常シナリオを基準に実績期間を評価し、当初想定との差（稼働日数・割合）、パーセンタイル、P90との差を表示します。

```bash
$ uv run spite predict --distribution lognormal --start-date 2024-09-10 --deadline 2024-09-30 --actual-end-date 2024-12-10 --output output.png
```

## ドキュメント

- [製品要求仕様書 (PRD)](docs/prd.ja.md) ([English](docs/prd.md))
- [アーキテクチャ決定記録 (ADR)](docs/adr.ja.md) ([English](docs/adr.md))

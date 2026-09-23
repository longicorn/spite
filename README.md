# Spite
Spiteはシステム開発における納期予測を確率分布に基づき行うための実験用ツール

既存の納期予測や工数管理等はせいぜい現場エンジニアの勘、ビジネス都合による要求、過去のスループットやサイクルタイムからの計算がよく行われる方法であり既存ツールもこの類似の考え方に寄っている

これを納期とは確率分布という考えを元に予測する方法があるが具体的にどう行うかは不明である。
これはシステム開発がそもそも多くの状況にありあまりにも複雑で再現性が難しいからだと考える。

Spiteのそのための実験的なツールとして方法を探るのが目的となる。

## 使い方

一旦仮で対数正規分布でのグラフ表示ができるように
考え方としては標準的な対数正規分布と終了日時指定可能な場合の計算&グラフ表示ができる

```
$ uv run spite predict
```

詳しい指定方法は `--help` 参照
```
$ uv run spite predict
```

```
# 開発未完了の場合
$ uv run spite predict --distribution lognormal --start-date 2024-09-10 --deadline 2024-09-30 --output output.png

# 開発完了済みの場合
$ uv run spite predict --distribution lognormal --start-date 2024-09-10 --deadline 2024-09-30 --actual-end-date 2024-12-10 --output output.png
```

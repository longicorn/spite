# 実装ドキュメント (spite predict / 対数正規分布版)

このドキュメントは、`docs/intent.md`・`docs/specification01.md` を前提として
実装した内容・設計判断・未実装事項をまとめたものです。
別セッションのAIがこのプロジェクトを引き継ぐ際は、まず
`docs/intent.md` → `docs/specification01.md` → 本ドキュメントの順に読むこと。

## 1. 現在の実装スコープ

- コマンドは `spite predict` のみ実装済み。
- 確率分布は **対数正規分布のみ** 実装済み。
  - スプライス分布(対数正規+GPD/Pareto)、Weibull分布は **未実装**。
    `spite predict` の動作確認が取れてから追加する方針(specification01.mdの
    処理1にある3分布のうち、対数正規分布のみを先行実装した状態)。
- 3シナリオ(楽観・基準・悲観)は **今回は対象外**。実装していない。
- 過去実績データの取り込み(`spite analyze` 等)は **未実装**。今回はゼロから
  分布を組み立てるデモ用途のみ。
- SQLite等によるDB記録は **未実装**(仕様書どおり今回は行わない)。
- 祝日は考慮しない。土日のみを非稼働日として扱う(1週間5日稼働)。
- パターン1(納期+最悪日を指定)の場合、比較しやすいようにパターン2の標準的な
  分布を自動で同じグラフに重ねて表示する(**実装済み**。詳細は2章・5章)。

## 2. コマンド仕様

```
spite predict --distribution lognormal --start-date YYYY-MM-DD [オプション]
```

- `--distribution` / `-d`: 現在は `lognormal` のみ選択可。**未指定なら predict の
  help を表示して終了**(仕様書の「未指定ならhelp表示して終了」に対応)。
- `--start-date`: 開発開始日。必須(未指定ならhelp表示して終了)。

### パターン1: 開始日 + 納期(mode) + 最悪日(P90)

```
--deadline YYYY-MM-DD --worst-case YYYY-MM-DD
```

両方セットで指定する必要がある(片方だけはエラー)。
`--median-days` / `--sigma` とは併用不可(エラーになる)。

### パターン2: 開始日のみ

`--deadline`/`--worst-case` を指定しない場合、既定のσ・中央値(後述)を使う。
`--median-days`, `--sigma` で個別に上書き可能。

### 出力先オプション

- 未指定: ターミナルへASCIIアートを表示(デフォルト)。
- `--output <path>`: 画像ファイル(png等)に保存。
- `--show`: matplotlibウィンドウで表示。
- 両方指定も可能(保存しつつウィンドウ表示)。

### パターン1指定時の比較グラフ表示(specification01.md追記分)

`docs/specification01.md` に「選択肢1では比較しやすいように選択肢2のグラフ
表示も行う」という要件が追記されたのに対応し、パターン1
(`--deadline`+`--worst-case`)指定時は、パターン2の既定値
(`DEFAULT_MEDIAN_BUSINESS_DAYS` / `DEFAULT_SIGMA` による標準的な分布)を
自動計算し、同じ出力(ASCII / matplotlib)に重ねて表示するようにした。

- 判定条件は `main()` 内の `is_choice1 = args.deadline is not None and
  args.worst_case is not None`。パターン2単独指定時は比較分布を計算しない
  (`comparison_params=None`)ため、**出力の見た目は従来と完全に同じ**。
- 比較用パラメータは常に `default_params()`(既定のmedian/sigma)を使う。
  パターン1指定時は `--median-days`/`--sigma` を併用できない仕様のため、
  ユーザーが独自の比較基準を指定する余地は現状ない。
- ASCII表示: 主分布を `#`、比較分布を `.` のバーとして横に並べて描画。
  比較分布側のパーセンタイルラベルには `(比較)` を付与して区別。
  出力先: `render_ascii()` (`src/spite/render.py`)。
- matplotlib表示: 主分布を青の実線、比較分布をオレンジの破線で重ね描き。
  パーセンタイルの縦線・ラベルも色と線種を分けて両方表示
  (比較分布側は末尾に `'` を付与、例: `P50'`)。タイトル・凡例ラベルも
  比較の有無で自動的に切り替わる。
  出力先: `render_matplotlib()` (`src/spite/render.py`)。
- 実装コミット: `feat: 選択肢1指定時に選択肢2の標準的な分布も比較表示する`。

## 3. 数式・パラメータ決定ロジック

対数正規分布のパラメータは `mu`(対数空間の平均), `sigma`(対数空間の標準偏差)。
`median = exp(mu)`, `mode = exp(mu - sigma^2)` の関係を利用している。

### パターン1(納期=mode, 最悪日=P90)

ユーザーとの合意事項: **「納期」は分布のピーク(mode)、「最悪でもこの日には
終わる/終えたい日」はP90相当** として扱う(intent.mdの3シナリオとは別の話。
今回はシナリオではなく単一分布内の話)。

lognormalの関係式:
```
mode = exp(mu - sigma^2)
P90  = exp(mu + Z_P90 * sigma)   (Z_P90 ≈ 1.2815515655446004: 標準正規分布の90%点)
```
この2式から `sigma` についての2次方程式が導ける:
```
sigma^2 + Z_P90 * sigma - ln(P90/mode) = 0
sigma = (-Z_P90 + sqrt(Z_P90^2 + 4*ln(P90/mode))) / 2   (正の解を採用)
mu = ln(mode) + sigma^2
```
実装: `src/spite/params.py` の `params_from_mode_and_p90()`。
`mode_days`, `p90_days` は開始日からの **稼働日数**(土日を除く)。
`p90_days <= mode_days` の場合はエラーとする(P90はmodeより後である前提)。

### パターン2(開始日のみ)のデフォルト値

**重要: μに数学的な「標準値」は存在しない。** μは実質的に期間そのもの
(median日数)を表すため、2週間の開発も2年の開発も両方あり得て絶対的な
「標準」が決められない。一方σは無次元の相対的ばらつきなので経験的な目安が
存在する。ユーザーとの合意で以下のデモ用デフォルト値とした:

```python
# src/spite/params.py に定数として定義済み(手動修正しやすい形)
DEFAULT_SIGMA: float = 0.5                    # 経験的レンジ0.3〜0.7の中間
DEFAULT_MEDIAN_BUSINESS_DAYS: float = 20.0    # 4週間相当。数学的根拠はなくデモ用の仮値
```

もしこれらの値を見直す場合は `src/spite/params.py` 冒頭のこの2定数だけを
書き換えれば良い(コード全体に散らばっていない)。

## 4. 土日(稼働日)の扱い

- 分布のパラメータ・計算はすべて **稼働日数ベース**(カレンダー日数ではない)。
- 日付が入力される箇所(`--deadline`, `--worst-case`)は、開始日からの稼働日数に
  変換してからパラメータ計算に使う(`business_days_between()`)。
- 結果(P50/P80/P90などの日数)を日付に戻す際も、稼働日をスキップしながら
  加算する(`add_business_days()`)。
- 実装は `src/spite/businessdays.py`。土日のみ非稼働日として判定
  (`weekday() < 5`)。祝日カレンダーは未対応。
- 実装は素朴なループ(1日ずつ判定)。日数が極端に大きい場合は遅くなりうるが、
  現状のユースケード(数ヶ月〜数年程度)では問題にならない。将来的に
  高速化する場合は `divmod` を使った週単位の計算に置き換えると良い。

## 5. ファイル構成

```
src/spite/
├── __init__.py       # main を re-export するだけ
├── cli.py            # spite predict のCLI本体(argparse, バリデーション, レポート出力)
├── params.py         # μ,σの定数とパラメータ算出ロジック(mode+P90 / median+sigma)
├── businessdays.py   # 稼働日計算(is_business_day, business_days_between, add_business_days)
├── lognormal.py       # scipy.stats.lognorm を使った統計量計算(percentile, summary_stats)
└── render.py          # ASCIIアート描画 / matplotlib描画(画像保存・ウィンドウ表示)
```

- `lognormal.py` の `scipy_dist()` は `scipy.stats.lognorm(s=sigma, scale=exp(mu))`
  というscipyのパラメータ化に対応させるアダプタ。
- `summary_stats()` は median, mode, mean, variance, stddev, skewness
  (歪度), kurtosis(超過尖度)を返す。specification01.mdの「尖度等」に対応。
- `render_ascii()` / `render_matplotlib()` はどちらも `comparison_params` /
  `comparison_percentiles` (共にオプション引数、既定 `None`) を受け取れる。
  `None` の場合は従来どおり単一分布のみ描画する(後方互換)。パターン1指定時
  の比較グラフ表示機能はこの引数を通じて `cli.py` から渡している
  (詳細は「2. コマンド仕様」の該当節を参照)。

## 6. 技術スタック・環境

- Python **3.13.15** に固定(`.python-version` および `pyproject.toml` の
  `requires-python`)。当初 `3.14.7` を指定していたが、最新すぎるバージョンで
  numpy/scipy/matplotlib等サードパーティ対応リスクを避けるため3.13系に変更した
  経緯がある。バージョンを変える場合は両ファイルをセットで直すこと。
- 依存パッケージ: `numpy`, `scipy`, `matplotlib`(`uv add` で追加、`uv.lock` に
  反映済み)。
- 実行は `uv run spite predict ...` を想定(README/会話ログ参照)。
- matplotlib画像出力で日本語ラベルが文字化け(tofu)しないよう、
  `render.py` で `font.family` に `Noto Sans CJK JP` を優先指定している。
  このフォントが存在しない環境では自動的に `sans-serif` にフォールバックする
  (文字化けする可能性はある)。

## 7. 動作確認済みの内容(手動確認、自動テストは未整備)

- 引数なし(`spite`, `spite predict`)でhelp表示。
- パターン1・パターン2それぞれでP50/P80/P90が日数・日付両方で正しく出る。
- `--deadline` のみ / `--worst-case` のみ指定時のエラー。
- パターン1とパターン2のオプションを混在させた場合のエラー
  (`--deadline`+`--median-days`など)。
- 不正な日付フォーマットのエラー。
- `--output` で画像保存、日本語ラベルが正しく表示されること(フォント対応後)。
- パターン1指定時、ASCII表示・`--output`画像出力の両方で選択肢2の比較分布が
  重ねて表示されること、パターン2単独指定時は従来どおり単一分布のみの表示に
  なること(手動でPNG出力して目視確認済み)。

**未整備:** pytest等の自動テストが無い。次に着手する際はまずテストを
書くことを推奨(特に `params.py` の数式が壊れていないかの回帰テスト)。

## 8. 未実装・今後の課題(intent.md / specification01.md との差分)

- スプライス分布(対数正規+GPD/Pareto)、Weibull分布の実装。
- 3シナリオ(楽観・基準・悲観)出力の実装。intent.mdでは
  「3シナリオ × 各シナリオのP50/P80/P90」が最終的な出力像として書かれている。
- 過去実績データ取り込み(`spite analyze`)、スプリント更新(`spite calculate`)、
  `spite init`, `spite start` は未着手。
- 祝日カレンダー対応。
- DB(SQLite)への記録。
- ストーリーポイントは仕様上使わない方針(intent.md参照)。実装上も未使用。

## 9. リポジトリ内の注意点(無関係なファイル)

以下は本実装と無関係、または経緯が不明なため一切変更していない。
別セッションのAIも誤って参照・削除しないよう注意すること。

- `aaa`: 用途不明のテキストファイル(未追跡)。
- `docs/probabilistic-delivery-forecasting-design.md`: `docs/intent.md` とは
  内容が異なる別ドラフト(未追跡)。本実装では参照していない。
  `intent.md`/`specification01.md` が正のドキュメントである。
- `report/ThePublicJiraDataset*`: intent.mdで言及されている公開Jiraデータセット
  のダウンロード物(未追跡)。今回の実装では未使用。
- `output0.png`, `output1.png`: 動作確認時に生成された画像ファイル(未追跡)。
  実装・ドキュメントとは無関係な生成物。
- `README.md`: 使い方の追記など、本ドキュメントの管理外で更新が入ることが
  ある(本記述時点で未コミットの変更が存在することがある)。変更履歴は
  `git log`/`git diff README.md` で都度確認すること。

## 10. Git状態・更新履歴(本ドキュメント更新時点)

`docs/specification01.md` は既にコミット済み(第9節の記述は古い情報だった
ため訂正済み)。関連コミット(新しい順):

- `feat: 選択肢1指定時に選択肢2の標準的な分布も比較表示する`
  — 本ドキュメント2章・5章に記載した比較グラフ表示機能。
- `docs: specification01.mdの見出し構造を整理して見やすくする`
  — 内容(仕様)は変えず、`###`/`####`見出し化と箇条書き化のみの整形。
- `docs: update docs/specification01.md`
  — 「選択肢1では比較しやすいように選択肢2のグラフ表示も行う」の要件追記。
  上記の比較グラフ表示機能はこの要件に対応するもの。
- `fix: フォントエラー対応`
- `docs: 初期版の仕様書を追加`
- `docs: spite predict実装の設計ドキュメントを追加`(本ファイルの初版)
- `feat: 対数正規分布によるspite predictコマンドを実装`(初期実装)

作業ブランチは引き続き `first_predict`。次セッションでの引き継ぎ時は
まず `git log --oneline -10` と `git status` で最新状態を確認すること
(本ドキュメントの内容が古くなっている可能性があるため)。

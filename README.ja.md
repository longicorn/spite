# Spite

[English Document](README.md)

Spiteは、システム開発における納期予測を確率分布に基づいて行うための実験用ツールです。

既存の納期予測や工数管理は、現場エンジニアの勘やビジネス都合の要求、あるいは過去のスループットやサイクルタイムからの計算に頼ることが多く、既存ツールもこれらの考え方に寄っています。「納期とは確率分布である」という考え方は以前から存在するものの、複雑なシステム開発の現場で具体的にどう扱うかは確立されていません。

Spiteは、開発初期から仮の確率分布を置いて3シナリオ（最善・通常・最悪）の予測を行い、完了後の実績と照らし合わせて予測手法を探求することを目的にしています。

## 使い方

Spiteには3つのコマンドがあります。

- `predict`は通常シナリオの想定期間から完了期間を予測します。
- `simulate`は仮のタスク依存関係、人数制限、作業の発見、手戻りを使って予測します。
- `history`は現在のブランチのGit履歴を調べ、保存した予測と比較できます。

periodは利用者が決める抽象的な期間で、例えば1スプリントに対応させられます。`--days-per-period`を指定すると、単純な倍率による概算日数を併記します。予測の完了日や祝日は計算しません。

### Predict

`--periods`は通常シナリオで最も起こりやすい期間、つまり最頻値です。中央値ではありません。`--actual-periods`を指定すると実績を振り返れます。

```bash
uv run spite predict --periods 6 --format markdown --output tmp/spite/
uv run spite predict --periods 6 --actual-periods 8 --days-per-period 5
```

### Simulate

`--tasks-per-period`はメンバー1人あたりのタスク数の基準です。その逆数を1タスクの所要期間の最頻値として使います。タスク期間にはばらつきがあるため、指定件数の完了を保証するものではありません。レビュー待ちは別に計算します。

```bash
uv run spite simulate --tasks-per-period 5 --days-per-period 5 --output tmp/spite/
uv run spite simulate --output tmp/spite/ --continue-from YOUR_RUN_ID --elapsed-periods 2 --completed-tasks 5 --remaining-tasks 8
```

再予測では把握している残タスクから仮のグラフを作ります。実際の完了済みタスクの依存関係や進行中の作業は復元しません。

### YAMLで指定した構造から予測する

テンプレートを生成し、プロジェクトに合わせて編集してから予測します。

```bash
uv run spite simulate --template > topology.yaml
uv run spite simulate --topology topology.yaml --team-size 2 --output tmp/spite/
```

例えば次のように記述します。

```yaml
elapsed_periods: 0
tasks:
  - id: explore
    name: 要件を調査
    kind: exploratory
    status: pending
    depends_on: []
  - id: build
    name: 実装
    kind: task
    status: pending
    depends_on: [explore]
  - id: review
    name: レビュー
    kind: gate
    status: pending
    depends_on: [build]
```

`elapsed_periods`は開始からの経過periodで、省略時は0です。各タスクには一意な文字列の`id`、`name`、`kind`、`status`、依存先IDのリスト`depends_on`が必要です。`kind`の`task`は開発作業、`exploratory`は追加作業を発見する可能性のある探索、`gate`はレビューや承認の待ちを表します。`status`は`pending`（未完了）または`completed`（完了済み）です。完了済みタスクは依存関係を満たし、再シミュレーションしません。進行中の作業は、残作業だけを表す未完了タスクとして記述します。依存先は存在し、循環してはならず、完了済みタスクは未完了タスクに依存できません。リストの上下は依存関係を意味しないため、`depends_on`で指定します。開始時の予測では、すべてのタスクを未完了にできます。

Git履歴から始める場合は`uv run spite simulate --from-git BASE > topology.yaml`を実行します。`BASE`にはコミット、ブランチ、タグを指定します。`BASE..HEAD`の非マージコミットを1件ずつ完了済みタスクにした下書きが生成されます。依存関係や経過期間は推定されず、未コミットの作業や将来の作業も含まれません。下書きを確認し、依存関係、残作業、探索タスクを追加してから予測してください。

後から予測を更新する場合は、YAMLの状態、残作業、`elapsed_periods`を編集し、再び`--topology`で実行します。レポートには残期間と合計期間が表示されます。YAMLによる予測に`--continue-from`は使えません。`--pattern`と`--scale`はYAMLが構造を指定するため、警告とともに無視されます。代表的な実行図の点線は担当者の空き待ちを表し、タスクの依存関係ではありません。詳しくは[Simulation PRD](docs/simulation/prd.ja.md)を参照してください。

### マージ後の履歴を調べる

対象リポジトリで**リリース先のブランチ**をチェックアウトして`history`を実行します。分析の終点は現在のブランチのHEADです。`--base`は分析を始める祖先コミットの指定で、マージされた機能ブランチを選択するオプションではありません。

例えば、複数の機能ブランチを`main`にマージした後、マージ前のリリースタグを起点にします。

```bash
git switch main
uv run spite history --base v1.0 --days-per-period 5 --output tmp/spite/
```

対象範囲は`base..HEAD`、つまりHEADからたどれてbaseからはたどれないコミットです。範囲内でマージされたブランチのコミットも含み、baseとその履歴は含みません。baseにはブランチ名、タグ、コミットIDを指定できます。`--base main`が現在のHEADを指す場合、対象は空です。マージ済みの機能ブランチの先端をbaseにすると、そのコミットと祖先が除外されるため、「そのブランチだけを分析する」という意味にはなりません。起点を固定したい場合は前回リリースのタグやコミットIDを使います。

マージ以外のコミットを観測された作業単位として数え、マージは別に数えます。Gitの親子関係は履歴上の構造であり、実際のタスク依存関係や同時作業を証明しません。squash mergeでは元のブランチが見えないこともあります。最初と最後のcommitter時刻の間隔には作業していない期間も含まれ、実際の開発期間ではありません。同じ出力ルートと`--days-per-period`を指定し、`--forecast-id YOUR_RUN_ID`を追加すると、この間隔を代用値として保存済みのSimulation予測と比較できます。Predictの予測には`--forecast-kind predict`を指定します。

### 実行結果の保存

`--output`にはルートディレクトリを指定します。各コマンドは`<root>/<command>/<run-id>/`に`report.md`と`snapshot.json`を保存し、形式によっては`chart.png`も保存します。省略時はレポートをターミナルに表示します。オプションの一覧は`uv run spite --help`または各サブコマンドの`--help`で確認できます。

## テスト

標準ライブラリのunittestでテストを実行します。

```bash
uv run python -m unittest discover -s tests
```

## ドキュメント

- [製品PRD](docs/prd.ja.md) ([English](docs/prd.md))と[ADR](docs/adr.ja.md) ([English](docs/adr.md))
- [Predict PRD](docs/predict/prd.ja.md) ([English](docs/predict/prd.md))と[ADR](docs/predict/adr.ja.md) ([English](docs/predict/adr.md))
- [Simulation PRD](docs/simulation/prd.ja.md) ([English](docs/simulation/prd.md))と[ADR](docs/simulation/adr.ja.md) ([English](docs/simulation/adr.md))
- [History PRD](docs/history/prd.ja.md) ([English](docs/history/prd.md))

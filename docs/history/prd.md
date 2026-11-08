# Product Requirements: Local Git History

[日本語版](prd.ja.md)

`spite history` reports the local Git history reachable from the current branch's HEAD after a specified ancestor commit or tag. It is intended for a branch representing a released state; Spite does not verify that a release occurred. A checked-out branch and an ancestor `--base` are required. `--base` accepts a branch name such as `master`, a tag, or a commit ID. The range is `base..HEAD`: commits reachable from HEAD but not from base, including merged branch commits. Base and its reachable history are excluded. Branch tips can move, so use a release tag or commit ID for a stable starting point. If base and HEAD are the same, the range is empty.

For a release branch containing multiple merged feature branches, check out the release destination and set `--base` to an ancestor before the merges, such as the previous release tag. Do not use `--base` to select an individual merged branch: its tip and ancestors are excluded from the range. `--base main` is empty when `main` is the current HEAD.

Each non-merge commit is one observed work unit. Merge commits are reported separately as joins. The report displays the parent graph, counts visible forks, and identifies a linear observed history or the presence of parallel paths. This describes Git topology, not proven task dependencies, branch names, or simultaneous work. Squash merges, rebases, cherry-picks, and unavailable or shallow history may obscure the original development structure.

The observation span is measured from the earliest to the latest committer timestamp among commits in range, in calendar days. It is not measured work duration: work may start before the first commit, timestamps may be edited, and the span includes weekends, holidays, and inactivity. Empty ranges have no span. `--days-per-period` optionally converts this span to approximate periods using a simple multiplier.

With `--output`, a report and versioned snapshot are saved under `history/<run-id>/` in the selected root. Without it, Markdown is printed. Optional `--forecast-id` loads a saved forecast from the same root; `--forecast-kind simulate` (default) or `predict` selects its type. Comparison requires `--days-per-period` and a nonempty range. The report displays the observed span beside the Nominal P50/P80/P90 forecast as a proxy, not an actual-duration evaluation. A continued simulation uses its total forecast including elapsed periods.

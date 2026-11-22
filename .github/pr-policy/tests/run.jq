# Usage: jq -n -L .github/pr-policy --slurpfile cases .github/pr-policy/tests/cases.json -f .github/pr-policy/tests/run.jq
include "policy";

def evaluate:
  . as $case
  | pr_files(
      {head: {sha: ($case.head_sha // "current")}, changed_files: ($case.count // ($case.pages | map(length) | add // 0))};
      $case.pages; "current")
  | if $case.check == "size" then size | [.additions, .deletions, .ignored] else components end;

[$cases[0][]
  | . as $case
  | (try {result: evaluate} catch {error: .}) as $outcome
  | if ($case | has("error")) then
      select(($outcome | has("error") | not) or ($outcome.error | contains($case.error) | not))
    else
      select($outcome != {result: $case.expect})
    end
  | {name: $case.name, expected: ($case.expect // {error: $case.error}), got: $outcome}]
| if length == 0 then "PASS: \($cases[0] | length) policy cases" else "\(tojson)\n" | halt_error(1) end

# Pull request policy: one application component per PR, at most 1,000 counted lines.
# Inputs come from the GitHub API: the PR object and `gh api --paginate --slurp` of
# its files. Every malformed or incomplete listing fails closed with error().

def lockfile: split("/") | last | IN("package-lock.json", "uv.lock");

def natural: type == "number" and . >= 0 and floor == .;

# The complete, validated file list of the PR at the expected head commit.
def pr_files($pr; $pages; $head):
  if $head == "" or ($pr.head.sha // null) != $head then
    error("PR head changed; the latest run must validate its changes.")
  elif ($pr.changed_files | natural | not) then
    error("GitHub did not return a valid changed-file count.")
  elif ($pages | type) != "array" or any($pages[]; type != "array") then
    error("GitHub did not return paginated PR files.")
  else
    [$pages[][]] as $files
    | if ($files | length) != $pr.changed_files then
        error("Incomplete PR file list; changes cannot be verified.")
      elif any($files[]; type != "object" or (.filename | type) != "string" or .filename == "") then
        error("GitHub returned an invalid PR file.")
      elif ($files | map(.filename) | unique | length) != ($files | length) then
        error("GitHub returned an empty or duplicate PR filename.")
      else $files
      end
  end;

def previous_path:
  if .status != "renamed" then empty
  elif (.previous_filename | type) == "string" and .previous_filename != "" then .previous_filename
  else error("Renamed file has no previous path; scope cannot be verified.")
  end;

# apps/backend/<name> or apps/<name>; shared files outside apps/ do not count.
def component:
  split("/") as $parts
  | if $parts[0:2] == ["apps", "backend"] then
      if ($parts | length) >= 4 then $parts[0:3] | join("/") else empty end
    elif ($parts | length) >= 3 and $parts[0] == "apps" then $parts[0:2] | join("/")
    else empty
    end;

# Renames count both the old and the new component.
def components: [.[] | (.filename, previous_path) | component] | unique;

# Generated lockfiles are excluded; renaming source code to a lockfile is not.
def size:
  reduce .[] as $file ({additions: 0, deletions: 0, ignored: 0};
    if ($file.additions | natural | not) or ($file.deletions | natural | not) then
      error("GitHub did not return valid PR line counts.")
    elif ($file.filename | lockfile) and ($file.status != "renamed" or ($file | previous_path | lockfile)) then
      .ignored += 1
    else
      .additions += $file.additions | .deletions += $file.deletions
    end)
  | .total = .additions + .deletions;

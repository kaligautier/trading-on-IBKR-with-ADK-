# Run through check.sh, which passes the budget, the consumer settings and any
# snapshot.sql inventory as jq variables.
include "capacity";

$budget[0] as $b
| (if $inventory == null then null elif ($inventory | type) == "array" then $inventory[0] else $inventory end) as $live
| ($b | budget_errors
    + source_errors($domains[0]; [$scanner, $reader, $momentum_api]; $litellm)
    + if $live != null then $b | inventory_errors($live; $release; $phase)
      elif ($release | length) > 0 or $phase == "migration" then ["A release requires a current full-visibility inventory"]
      else [] end) as $errors
| if $errors == [] then $b | summary
  else "Capacity validation failed:\n- \($errors | join("\n- "))\n" | halt_error(1) end

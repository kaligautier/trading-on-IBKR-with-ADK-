# Refuse a Terraform plan that does anything but update the image of Cloud Run workloads.
#
# Input: `terraform show -json` of the release plan.
# Data: data.deploy.repository, the image repository every changed container must use,
# pinned by a sha256 digest. Messages name resource addresses and attribute paths only:
# plan values never reach the (public) log.
package main

import rego.v1

workloads := {"google_cloud_run_v2_service", "google_cloud_run_v2_job"}

# Provider bookkeeping that disappears once Terraform owns the resource.
noise := {"client", "client_version"}

image_path := `^template\.0(\.template\.0)?\.containers\.\d+\.image$`

digest := `^@sha256:[0-9a-f]{64}$`

changes contains resource if {
	some resource in input.resource_changes
	not resource.change.actions in [["no-op"], ["read"]]
}

in_place_workload(resource) if {
	resource.change.actions == ["update"]
	resource.type in workloads
}

deny contains msg if {
	some resource in changes
	not in_place_workload(resource)
	msg := sprintf("%s: %s is not an in-place Cloud Run update", [resource.address, concat(",", resource.change.actions)])
}

# --- Attribute diff, matching the paths `before` and `after` disagree on. -------------

value(document, path) := object.get(document, path, null)

both_objects(a, b) if {
	is_object(a)
	is_object(b)
}

same_length_arrays(a, b) if {
	is_array(a)
	is_array(b)
	count(a) == count(b)
}

# The comparison stops at a path that is not two objects or two arrays of equal length.
terminal(change, path) if {
	before := value(change.before, path)
	after := value(change.after, path)
	not both_objects(before, after)
	not same_length_arrays(before, after)
}

differs(change, path) if {
	before := value(change.before, path)
	after := value(change.after, path)
	is_array(before)
	is_array(after)
	count(before) != count(after)
}

differs(change, path) if {
	before := value(change.before, path)
	after := value(change.after, path)
	not both_arrays(before, after)
	before != after
}

both_arrays(a, b) if {
	is_array(a)
	is_array(b)
}

# Values unknown until apply (after_unknown = true on the path or a parent) are ignored.
unknown(change, path) if {
	some length in numbers.range(0, count(path))
	object.get(object.get(change, "after_unknown", {}), array.slice(path, 0, length), false) == true
}

below_terminal(change, path) if {
	some length in numbers.range(0, count(path) - 1)
	terminal(change, array.slice(path, 0, length))
}

candidates(change) := {path | walk(change.before, [path, _])} | {path | walk(change.after, [path, _])}

changed_paths(change) := {concat(".", [sprintf("%v", [part]) | some part in path]) |
	some path in candidates(change)
	count(path) > 0
	terminal(change, path)
	differs(change, path)
	not unknown(change, path)
	not below_terminal(change, path)
}

# --- Rules on in-place updates of Cloud Run workloads. --------------------------------

relevant_paths(resource) := {path | some path in changed_paths(resource.change); not path in noise}

image_paths(resource) := {path | some path in relevant_paths(resource); regex.match(image_path, path)}

deny contains msg if {
	some resource in changes
	in_place_workload(resource)
	some path in relevant_paths(resource)
	not regex.match(image_path, path)
	msg := sprintf("%s: `%s` changes besides the image", [resource.address, path])
}

pinned(image) if {
	is_string(image)
	startswith(image, data.deploy.repository)
	regex.match(digest, substring(image, count(data.deploy.repository), -1))
}

deny contains msg if {
	some resource in changes
	in_place_workload(resource)
	some path in image_paths(resource)
	not pinned(value(resource.change.after, [segment(part) | some part in split(path, ".")]))
	msg := sprintf("%s: `%s` is not %s pinned by a sha256 digest", [resource.address, path, data.deploy.repository])
}

segment(part) := to_number(part) if regex.match(`^\d+$`, part)

segment(part) := part if not regex.match(`^\d+$`, part)

deny contains msg if {
	some resource in changes
	in_place_workload(resource)
	count(relevant_paths(resource)) == 0
	msg := sprintf("%s: updated without an image change", [resource.address])
}

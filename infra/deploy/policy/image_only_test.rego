package main

import rego.v1

repeat64(char) := concat("", [char | some _ in numbers.range(1, 64)])

repository := "europe-west1-docker.pkg.dev/p/market-scanner/app"

old := concat("", [repository, "@sha256:", repeat64("a")])

new := concat("", [repository, "@sha256:", repeat64("b")])

service_with(image, env_after) := {
	"address": "google_cloud_run_v2_service.svc",
	"type": "google_cloud_run_v2_service",
	"change": {
		"actions": ["update"],
		"before": {
			"name": "svc", "client": "gcloud",
			"template": [{"containers": [{"image": old, "env": [{"name": "A", "value": "x"}]}]}],
		},
		"after": {
			"name": "svc",
			"template": [{"containers": [{"image": image, "env": [{"name": "A", "value": env_after}]}]}],
		},
		"after_unknown": {"etag": true, "template": [{"revision": true}]},
	},
}

service := service_with(new, "x")

result(resources) := problems if {
	problems := deny with input as {"resource_changes": resources}
		with data.deploy.repository as repository
}

test_accepts_a_digest_pinned_image_update if count(result([service])) == 0

test_accepts_a_job_with_the_nested_template if {
	job := {
		"address": "google_cloud_run_v2_job.j",
		"type": "google_cloud_run_v2_job",
		"change": {
			"actions": ["update"],
			"before": {"template": [{"template": [{"containers": [{"image": old}]}]}]},
			"after": {"template": [{"template": [{"containers": [{"image": new}]}]}]},
			"after_unknown": {},
		},
	}
	count(result([job])) == 0
}

test_ignores_unchanged_resources if {
	noop := {"address": "x", "type": "google_project", "change": {"actions": ["no-op"]}}
	read := {"address": "y", "type": "google_project", "change": {"actions": ["read"]}}
	count(result([noop, read, service])) == 0
}

test_refuses_another_change_in_the_same_resource if {
	problems := result([service_with(new, "y")])
	count(problems) == 1
	some problem in problems
	contains(problem, "`template.0.containers.0.env.0.value` changes besides the image")
}

test_refuses_create_delete_and_replace if {
	every actions in [["create"], ["delete"], ["delete", "create"], ["create", "delete"]] {
		count(result([object.union(service, {"change": object.union(service.change, {"actions": actions})})])) == 1
	}
}

test_refuses_other_resource_types if {
	secret := object.union(service, {"type": "google_secret_manager_secret", "address": "google_secret_manager_secret.s"})
	count(result([secret])) == 1
}

test_refuses_a_tag_or_another_repository if {
	every image in [
		concat("", [repository, ":latest"]),
		concat("", [repository, "@sha256:abc"]),
		concat("", ["other/", repository, "@sha256:", repeat64("c")]),
		concat("", [repository, "-evil@sha256:", repeat64("c")]),
	] {
		count(result([service_with(image, "x")])) == 1
	}
}

test_refuses_a_second_container_change if {
	two := json.patch(service, [
		{"op": "add", "path": "/change/before/template/0/containers/-", "value": {"image": old}},
		{"op": "add", "path": "/change/after/template/0/containers/-", "value": {"image": concat("", [new, "x"])}},
	])
	count(result([two])) > 0
}

test_refuses_an_added_container if {
	added := json.patch(service, [{"op": "add", "path": "/change/after/template/0/containers/-", "value": {"image": new}}])
	count(result([added])) > 0
}

test_refuses_an_update_without_image_change if {
	problems := result([service_with(old, "x")])
	problems == {"google_cloud_run_v2_service.svc: updated without an image change"}
}

test_values_unknown_until_apply_are_ignored if {
	etag := json.patch(service, [{"op": "add", "path": "/change/before/etag", "value": "old"}])
	count(result([etag])) == 0
}

test_never_prints_plan_values if {
	problems := result([service_with(new, "TOP-SECRET")])
	count(problems) > 0
	every problem in problems {
		not contains(problem, "TOP-SECRET")
	}
}

test_an_empty_plan_is_accepted if {
	count(result([])) == 0
	count(deny) == 0 with input as {} with data.deploy.repository as repository
}

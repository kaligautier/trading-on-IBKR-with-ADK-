import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import check_image_only_plan as guard  # noqa: E402

REPO = "europe-west1-docker.pkg.dev/p/market-scanner/app"
OLD = f"{REPO}@sha256:{'a' * 64}"
NEW = f"{REPO}@sha256:{'b' * 64}"


def service(image=NEW, env="x"):
    before = {
        "name": "svc",
        "client": "gcloud",
        "template": [
            {"containers": [{"image": OLD, "env": [{"name": "A", "value": env}]}]}
        ],
    }
    after = {
        "name": "svc",
        "template": [
            {"containers": [{"image": image, "env": [{"name": "A", "value": env}]}]}
        ],
    }
    return {
        "address": "google_cloud_run_v2_service.svc",
        "type": "google_cloud_run_v2_service",
        "change": {
            "actions": ["update"],
            "before": before,
            "after": after,
            "after_unknown": {"etag": True, "template": [{"revision": True}]},
        },
    }


def plan(*resources):
    return {"resource_changes": list(resources)}


class ImageOnlyPlan(unittest.TestCase):
    def test_accepts_a_digest_pinned_image_update(self):
        problems, changes = guard.check(plan(service()), REPO)
        self.assertEqual(problems, [])
        self.assertEqual(len(changes), 1)

    def test_accepts_a_job_with_the_nested_template(self):
        resource = {
            "address": "google_cloud_run_v2_job.j",
            "type": "google_cloud_run_v2_job",
            "change": {
                "actions": ["update"],
                "before": {
                    "template": [{"template": [{"containers": [{"image": OLD}]}]}]
                },
                "after": {
                    "template": [{"template": [{"containers": [{"image": NEW}]}]}]
                },
                "after_unknown": {},
            },
        }
        self.assertEqual(guard.check(plan(resource), REPO)[0], [])

    def test_ignores_unchanged_resources(self):
        noop = {
            "address": "x",
            "type": "google_project",
            "change": {"actions": ["no-op"]},
        }
        self.assertEqual(guard.check(plan(noop, service()), REPO)[0], [])

    def test_refuses_another_change_in_the_same_resource(self):
        resource = service()
        resource["change"]["after"]["template"][0]["containers"][0]["env"][0][
            "value"
        ] = "y"
        problems, _ = guard.check(plan(resource), REPO)
        self.assertEqual(len(problems), 1)
        self.assertIn("env.0.value", problems[0])

    def test_refuses_create_delete_and_replace(self):
        for actions in (
            ["create"],
            ["delete"],
            ["delete", "create"],
            ["create", "delete"],
        ):
            resource = service()
            resource["change"]["actions"] = actions
            self.assertEqual(len(guard.check(plan(resource), REPO)[0]), 1, actions)

    def test_refuses_other_resource_types(self):
        resource = service()
        resource["type"] = "google_secret_manager_secret"
        resource["address"] = "google_secret_manager_secret.s"
        self.assertEqual(len(guard.check(plan(resource), REPO)[0]), 1)

    def test_refuses_a_tag_or_another_repository(self):
        for image in (
            f"{REPO}:latest",
            f"{REPO}@sha256:abc",
            f"other/{REPO}@sha256:{'c' * 64}",
            f"{REPO}-evil@sha256:{'c' * 64}",
        ):
            self.assertEqual(
                len(guard.check(plan(service(image=image)), REPO)[0]), 1, image
            )

    def test_refuses_a_second_container_change(self):
        resource = service()
        for side in ("before", "after"):
            resource["change"][side]["template"][0]["containers"].append(
                {"image": OLD if side == "before" else NEW + "x"}
            )
        self.assertTrue(guard.check(plan(resource), REPO)[0])

    def test_refuses_an_added_container(self):
        resource = service()
        resource["change"]["after"]["template"][0]["containers"].append({"image": NEW})
        self.assertTrue(guard.check(plan(resource), REPO)[0])

    def test_refuses_an_update_without_image_change(self):
        resource = service(image=OLD)
        self.assertEqual(len(guard.check(plan(resource), REPO)[0]), 1)

    def test_values_unknown_until_apply_are_ignored(self):
        resource = service()
        resource["change"]["before"]["etag"] = "old"
        self.assertEqual(guard.check(plan(resource), REPO)[0], [])

    def test_never_prints_plan_values(self):
        resource = service()
        resource["change"]["after"]["template"][0]["containers"][0]["env"][0][
            "value"
        ] = "TOP-SECRET"
        problems, _ = guard.check(plan(resource), REPO)
        self.assertTrue(problems)
        self.assertNotIn("TOP-SECRET", "\n".join(problems))

    def test_an_empty_plan_is_accepted_with_no_change(self):
        self.assertEqual(guard.check(plan(), REPO), ([], []))
        self.assertEqual(copy.deepcopy(plan()), plan())


if __name__ == "__main__":
    unittest.main()

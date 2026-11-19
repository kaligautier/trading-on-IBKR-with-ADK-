import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import release  # noqa: E402

OLD = "sha256:" + "a" * 64
NEW = "sha256:" + "b" * 64


class ReleaseConfig(unittest.TestCase):
    def test_every_root_is_complete_and_digest_free(self):
        releases = json.loads((HERE.parent / "releases.json").read_text())
        self.assertEqual(
            set(releases), {"market-scanner", "reader", "momentum-api", "momentum"}
        )
        for root, entry in releases.items():
            for key in release.KEYS:
                self.assertTrue(entry[key], f"{root}.{key}")
            self.assertNotIn("@", entry["image"], root)
            self.assertIn(entry["release_file"], entry["plan_vars"], root)
            self.assertTrue(
                (HERE.parents[2] / entry["app"] / "Dockerfile").exists(), root
            )
            self.assertTrue(
                (HERE.parents[1] / root / entry["release_file"]).exists(), root
            )

    def test_release_files_hold_one_pinned_image_of_the_declared_repository(self):
        releases = json.loads((HERE.parent / "releases.json").read_text())
        for root, entry in releases.items():
            text = (HERE.parents[1] / root / entry["release_file"]).read_text()
            matches = release.IMAGE_LINE.findall(text)
            self.assertEqual(len(matches), 1, root)
            self.assertTrue(
                matches[0][0].split('"')[1].startswith(entry["image"] + "@"), root
            )

    def test_unknown_root_is_refused(self):
        with self.assertRaises(SystemExit):
            release.config_lines("litellm")

    def test_config_lines(self):
        lines = release.config_lines("momentum")
        self.assertIn("prefix=preprod/momentum", lines)
        self.assertTrue(
            any(line.startswith("plan_vars=config/preprod.tfvars ") for line in lines)
        )


class Record(unittest.TestCase):
    def write(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".tfvars", delete=False)
        handle.write(text)
        handle.close()
        self.addCleanup(pathlib.Path(handle.name).unlink)
        return handle.name

    def test_pins_the_new_digest_and_keeps_the_rest(self):
        path = self.write(f'# comment\nimage = "r/app@{OLD}"\nregion = "x"\n')
        release.record(path, NEW)
        self.assertEqual(
            pathlib.Path(path).read_text(),
            f'# comment\nimage = "r/app@{NEW}"\nregion = "x"\n',
        )

    def test_refuses_a_tag(self):
        with self.assertRaises(SystemExit):
            release.record(self.write(f'image = "r/app@{OLD}"\n'), "latest")

    def test_refuses_zero_or_several_image_lines(self):
        for text in (
            "region = 1\n",
            f'image = "r/a@{OLD}"\nimage = "r/b@{OLD}"\n',
            'image = "r/app:tag"\n',
        ):
            with self.assertRaises(SystemExit):
                release.record(self.write(text), NEW)


if __name__ == "__main__":
    unittest.main()

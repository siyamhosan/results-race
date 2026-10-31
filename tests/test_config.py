"""Configuration precedence and validation: defaults < config file < environment < command line."""
import copy
import os
import tempfile
import unittest
from pathlib import Path

from results_race.config import Config, ConfigError, load, dump


def write(text, name="results-race.toml"):
    d = Path(tempfile.mkdtemp())
    (d / name).write_text(text)
    return d / name


def same_but_paths(c):
    """Relative paths read from a file resolve next to that file, so compare only the folder name."""
    c = copy.deepcopy(c)
    c.output.dir = Path(c.output.dir).name
    return c


def cfg_for(argv=(), env=None, toml=None):
    """Load a config in a bare room: an empty working folder and home, so a developer's own results-race.toml
    (auto-discovered in the current folder or ~/.config) and RESULTS_* variables can never leak into a test."""
    old_env, old_cwd = dict(os.environ), os.getcwd()
    for k in list(os.environ):
        if k.startswith("RESULTS_"):
            del os.environ[k]
    bare = tempfile.mkdtemp()
    os.environ["HOME"] = bare
    os.environ.update(env or {})
    os.chdir(bare)
    try:
        args = list(argv) + (["--config", str(write(toml))] if toml is not None else [])
        return load(args)[0]
    finally:
        os.chdir(old_cwd)
        os.environ.clear()
        os.environ.update(old_env)


class ConfigTest(unittest.TestCase):
    def test_everything_has_a_default_so_zero_config_works(self):
        c = cfg_for()
        self.assertEqual((c.run.board, c.run.exam, c.run.year), ("rajshahi", "hsc", "2026"))
        self.assertEqual(len(c.sites.urls), 3)
        self.assertEqual((c.server.host, c.server.auth, c.students.file, c.proxies.file), ("127.0.0.1", "", "", ""))
        self.assertEqual((c.ui.credit, c.card.credit), ("BazarLab by Siyam", "BazarLab by Siyam"))

    def test_file_overrides_default(self):
        c = cfg_for(toml='[run]\nexam = "ssc"\nyear = 2024\n[hedge]\nseconds = 0\n')
        self.assertEqual((c.run.exam, c.run.year, c.hedge.seconds), ("ssc", "2024", 0))  # year given as a number is fine

    def test_environment_overrides_file_and_cli_overrides_environment(self):
        toml = '[run]\nexam = "ssc"\n'
        self.assertEqual(cfg_for(toml=toml, env={"RESULTS_RACE_RUN_EXAM": "jsc"}).run.exam, "jsc")
        self.assertEqual(cfg_for(["--exam", "hsc"], toml=toml, env={"RESULTS_RACE_RUN_EXAM": "jsc"}).run.exam, "hsc")

    def test_generic_set_flag_reaches_every_option(self):
        c = cfg_for(["--set", "ui.theme=dark", "--set", "card.png_scale=2", "--set", "students.allow_manual_add=false"])
        self.assertEqual((c.ui.theme, c.card.png_scale, c.students.allow_manual_add), ("dark", 2, False))

    def test_lists_come_from_json_or_commas(self):
        self.assertEqual(cfg_for(env={"RESULTS_RACE_SITES_URLS": "https://a.test,https://b.test"}).sites.urls,
                         ["https://a.test", "https://b.test"])
        self.assertEqual(cfg_for(["--set", 'notify.command=["echo","{url}"]']).notify.command, ["echo", "{url}"])

    def test_unknown_option_is_an_error_that_names_the_valid_ones(self):
        with self.assertRaises(ConfigError) as cm:
            cfg_for(toml='[run]\nexamm = "ssc"\n')
        self.assertIn("examm", str(cm.exception))
        self.assertIn("exam", str(cm.exception))
        with self.assertRaises(ConfigError):
            cfg_for(toml='[nope]\nx = 1\n')

    def test_relative_paths_in_a_config_file_are_relative_to_that_file(self):
        path = write('[students]\nfile = "list.json"\n[output]\ndir = "results"\n')
        c = cfg_for(["--config", str(path)])
        self.assertEqual(Path(c.students.file), path.parent / "list.json")
        self.assertEqual(Path(c.output.dir), path.parent / "results")

    def test_invalid_values_are_rejected(self):
        for argv in (["--set", "ui.theme=neon"], ["--set", "sites.lanes_per_site=0"], ["--set", "server.port=99999"],
                     ["--set", "server.auth=nopassword"], ["--set", "hedge.seconds=-1"], ["--set", "card.png_scale=9"]):
            with self.assertRaises(ConfigError, msg=argv):
                cfg_for(argv)

    def test_serving_the_lan_needs_a_password_or_an_explicit_opt_out(self):
        with self.assertRaises(ConfigError):
            cfg_for(["--host", "0.0.0.0"])
        self.assertEqual(cfg_for(["--host", "0.0.0.0", "--no-auth"]).server.host, "0.0.0.0")
        self.assertEqual(cfg_for(["--host", "0.0.0.0"], env={"RESULTS_AUTH": "me:pw"}).server.auth, "me:pw")  # legacy alias

    def test_the_documented_example_file_equals_the_defaults(self):
        example = Path(__file__).parent.parent / "config.example.toml"
        self.assertEqual(same_but_paths(cfg_for(["--config", str(example)])), Config())

    def test_the_packaged_example_is_the_documented_one(self):
        root = Path(__file__).parent.parent
        self.assertEqual((root / "config.example.toml").read_text(), (root / "src/results_race/config.example.toml").read_text())

    def test_dump_round_trips(self):
        c = cfg_for(["--exam", "ssc", "--set", "ui.title=My results"])
        self.assertEqual(same_but_paths(cfg_for(["--config", str(write(dump(c)))])), same_but_paths(c))


unittest.main() if __name__ == "__main__" else None

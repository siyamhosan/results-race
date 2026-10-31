import tempfile
import unittest
from pathlib import Path

from results_race.config import DEFAULT_SITES as SITES
from results_race.engine import build_lanes
from results_race.proxies import load_proxies


def write(text):
    f = Path(tempfile.mkdtemp()) / "proxy.txt"
    f.write_text(text)
    return f


class ProxyFileTest(unittest.TestCase):
    def test_formats_comments_and_blanks(self):
        ps = load_proxies(write("# comment\n\n1.2.3.4:8080\nsocks5://5.6.7.8:1080\nhttp://bob:pw@9.9.9.9:3128\n10.0.0.1:80:ann:secret\n"))
        self.assertEqual([p.server for p in ps], ["http://1.2.3.4:8080", "socks5://5.6.7.8:1080", "http://9.9.9.9:3128", "http://10.0.0.1:80"])
        self.assertEqual([(p.user, p.password) for p in ps], [(None, None), (None, None), ("bob", "pw"), ("ann", "secret")])

    def test_missing_file_means_no_proxies(self):
        self.assertEqual(load_proxies(Path("/nonexistent/proxy.txt")), [])

    def test_bad_line_is_reported_not_silently_used(self):
        with self.assertRaises(ValueError):
            load_proxies(write("not a proxy\n"))


class LaneBuildTest(unittest.TestCase):
    def test_each_lane_gets_a_proxied_twin_per_proxy(self):
        ps = load_proxies(write("1.1.1.1:80\n2.2.2.2:80\n"))
        lanes = build_lanes(None, SITES, 2, ps)
        self.assertEqual(len(lanes), 3 * 2 * (1 + 2))
        self.assertEqual(sum(1 for l in lanes if l.proxy is None), 6)
        self.assertEqual(len({l.id for l in lanes}), len(lanes))  # ids unique
        self.assertTrue(all(l.proxy for l in lanes if "-p" in l.id))

    def test_proxies_sharing_one_gateway_still_get_distinct_lane_ids(self):
        ps = load_proxies(write("http://a:1@gw.example.com:9999\nhttp://b:2@gw.example.com:9999\nhttp://c:3@gw.example.com:9999\n"))
        lanes = build_lanes(None, SITES, 2, ps)
        self.assertEqual(len(lanes), 24)
        self.assertEqual(len({l.id for l in lanes}), 24)

    def test_no_proxies_means_only_direct_lanes(self):
        self.assertEqual(len(build_lanes(None, SITES, 2, [])), 6)


unittest.main() if __name__ == "__main__" else None

import base64
import unittest

from results_race.auth import authorized


def basic(user, pw):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


class AuthTest(unittest.TestCase):
    def test_correct_login_passes(self):
        self.assertTrue(authorized(basic("me", "s3cret"), "me:s3cret"))

    def test_wrong_password_user_or_missing_header_fail(self):
        for header in [basic("me", "nope"), basic("you", "s3cret"), None, "", "Bearer abc", "Basic !!!notbase64", "Basic "]:
            self.assertFalse(authorized(header, "me:s3cret"), header)

    def test_password_may_contain_colons(self):
        self.assertTrue(authorized(basic("me", "a:b:c"), "me:a:b:c"))

    def test_no_configured_login_means_closed_not_open(self):
        self.assertFalse(authorized(basic("", ""), ""))
        self.assertFalse(authorized(None, None))


unittest.main() if __name__ == "__main__" else None

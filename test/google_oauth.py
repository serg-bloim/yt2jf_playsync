import unittest

from oauth import relogin_users


class MyTestCase(unittest.TestCase):
    def test_send_link_all_users(self):
        relogin_users()


if __name__ == '__main__':
    unittest.main()

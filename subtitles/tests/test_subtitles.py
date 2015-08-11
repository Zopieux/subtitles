from unittest import TestCase

from subtitles import __main__ as main


class TestSlugify(TestCase):
    def setUp(self):
        self.s = main.slugify

    def test_defaults(self):
        self.assertEqual(self.s('foo BAR baz', ok='-'), 'foo-bar-baz')
        self.assertEqual(self.s('foo BAR baz', ok='-', lower=False), 'foo-BAR-baz')

    def test_ok(self):
        self.assertEqual(self.s('foo BAR baz', ok='-'), 'foo-bar-baz')
        self.assertEqual(self.s('foo BAR baz', ok='!'), 'foo!bar!baz')
        self.assertEqual(self.s('foo BAR baz', ok=' '), 'foo bar baz')
        self.assertEqual(self.s('FOO BAR.baz', ok='-_'), 'foo-bar-baz')
        self.assertEqual(self.s('FOO BAR.baz', ok='_-'), 'foo_bar_baz')

    def test_contiguous(self):
        self.assertEqual(self.s('FOO BAR..  ..baz', ok='-_'), 'foo-bar-baz')


class TestOpensubtitles(TestCase):
    def setUp(self):
        self.client = main.Opensubtitles()

    def test_login(self):
        self.assertFalse(self.client.token)
        self.client.login()
        self.assertTrue(self.client.token)

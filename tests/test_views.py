"""Run with python3 tests/test_views.py (requires Playwright and Chromium)."""
import unittest
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
HOME = 'https://shishishu.github.io/'


class ViewCountTests(unittest.TestCase):
    def setUp(self):
        pw = sync_playwright().start()
        self.addCleanup(pw.stop)
        browser = pw.chromium.launch()
        self.addCleanup(browser.close)
        self.context = browser.new_context()
        self.page = self.context.new_page()
        self.hits = 0
        self.reads = 0
        self.total = 40
        self.lose_hit_response = False
        self.fail_read = False
        self.context.route(HOME + '**', self.static_file)
        self.context.route('https://abacus.jasoncameron.dev/**', self.counter)

    def static_file(self, route):
        path = route.request.url.removeprefix(HOME) or 'index.html'
        route.fulfill(path=ROOT / path)

    def counter(self, route):
        path = route.request.url.split('/')
        if path[-1] == 'likes':
            route.fulfill(json={'value': 0})
            return
        self.assertEqual(path[-2:], ['shishishu.github.io', 'views'])
        if path[-3] == 'hit':
            self.hits += 1
            self.total += 1
            if self.lose_hit_response:
                route.abort()
                return
        else:
            self.assertEqual(path[-3], 'get')
            self.reads += 1
            if self.fail_read:
                route.fulfill(status=503, body='')
                return
        route.fulfill(json={'value': self.total})

    def test_reopen_with_counter_outage_and_recovery(self):
        self.page.goto(HOME)
        expect(self.page.locator('#view-count')).to_have_text('41')
        self.page.close()
        self.lose_hit_response = self.fail_read = True
        self.page = self.context.new_page()
        with self.page.expect_response('**/get/*/views'):
            self.page.goto(HOME)
        expect(self.page.locator('#view-count')).to_have_text('41')
        self.fail_read = False
        self.page.reload()
        expect(self.page.locator('#view-count')).to_have_text('43')
        self.assertEqual((self.hits, self.reads), (3, 2))

    def test_first_visit_during_outage(self):
        self.lose_hit_response = self.fail_read = True
        self.page.goto(HOME)
        expect(self.page.locator('#view-count')).to_have_text('unavailable')
        self.assertEqual((self.hits, self.reads), (1, 1))

    def test_storage_blocked(self):
        self.page.add_init_script(
            "Object.defineProperty(window, 'localStorage', {get() {throw Error('blocked')}})"
        )
        self.page.goto(HOME)
        expect(self.page.locator('#view-count')).to_have_text('41')

    def test_slow_update_keeps_saved_count_visible(self):
        self.page.goto(HOME)
        expect(self.page.locator('#view-count')).to_have_text('41')
        pending = []
        self.page.clock.install()
        self.page.route('**/hit/*/views', lambda route: pending.append(route))
        with self.page.expect_request('**/hit/*/views'):
            self.page.reload(wait_until='domcontentloaded')
        self.page.clock.fast_forward(15000)
        expect(self.page.locator('#view-count')).to_have_text('41')
        pending[0].fulfill(json={'value': 42})
        expect(self.page.locator('#view-count')).to_have_text('42')
        self.assertEqual(self.reads, 0)

    def test_other_tab_shares_newer_count(self):
        self.page.goto(HOME)
        expect(self.page.locator('#view-count')).to_have_text('41')
        other = self.context.new_page()
        other.goto(HOME)
        expect(other.locator('#view-count')).to_have_text('42')
        expect(self.page.locator('#view-count')).to_have_text('42')


if __name__ == '__main__':
    unittest.main()

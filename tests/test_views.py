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
        self.addCleanup(self.context.close)
        self.addCleanup(self.context.unroute_all, behavior="wait")
        self.page = self.context.new_page()
        self.hits = 0
        self.reads = 0
        self.like_total = 12
        self.like_hits = 0
        self.fail_like_read = False
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
            if path[-3] == 'hit':
                self.like_hits += 1
                self.like_total += 1
            elif self.fail_like_read:
                route.fulfill(status=503, body='')
                return
            route.fulfill(json={'value': self.like_total})
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

    def test_reader_keeps_like_total_during_outage(self):
        self.like_total = 0
        self.page.goto(HOME)
        count = self.page.locator('#like-count')
        expect(count).to_have_text('0')
        self.fail_like_read = True
        self.page.reload(wait_until='networkidle')
        expect(count).to_have_text('0')
        expect(self.page.locator('#like-button')).to_be_enabled()
        self.fail_like_read = False
        self.like_total = 13
        self.page.reload()
        expect(count).to_have_text('13')
        self.assertEqual(self.like_hits, 0)

    def test_existing_like_survives_failed_read(self):
        self.page.add_init_script("localStorage.setItem('homepage-liked', '12')")
        self.fail_like_read = True
        self.page.goto(HOME)
        expect(self.page.locator('#like-count')).to_have_text('12')
        expect(self.page.locator('#like-button')).to_be_disabled()
        self.assertEqual(self.like_hits, 0)

    def test_like_and_reopen_with_stale_read_in_another_tab(self):
        self.page.goto(HOME)
        expect(self.page.locator('#like-count')).to_have_text('12')
        other = self.context.new_page()
        pending = []
        other.route('**/get/*/likes', lambda route: pending.append(route))
        with other.expect_request('**/get/*/likes'):
            other.goto(HOME, wait_until='domcontentloaded')
        self.page.locator('#like-button').click()
        expect(other.locator('#like-count')).to_have_text('13')
        pending[0].fulfill(json={'value': 12})
        expect(other.locator('#like-button')).to_have_attribute('aria-label', 'You liked this page. Likes: 13')
        other.unroute('**/get/*/likes')
        self.page.close()
        self.fail_like_read = True
        other.reload(wait_until='networkidle')
        expect(other.locator('#like-count')).to_have_text('13')
        expect(other.locator('#like-button')).to_be_disabled()
        self.assertEqual(self.like_hits, 1)

    def test_pending_click_and_late_read_do_not_submit_twice(self):
        pending_reads = []
        pending_hits = []
        self.page.route('**/get/*/likes', lambda route: pending_reads.append(route))
        self.page.route('**/hit/*/likes', lambda route: pending_hits.append(route))
        with self.page.expect_request('**/get/*/likes'):
            self.page.goto(HOME, wait_until='domcontentloaded')
        button = self.page.locator('#like-button')
        with self.page.expect_request('**/hit/*/likes'):
            button.click()
        pending_reads[0].fulfill(json={'value': 12})
        expect(self.page.locator('#like-count')).to_have_text('12')
        expect(button).to_be_disabled()
        button.evaluate("button => button.click()")
        pending_hits[0].fulfill(json={'value': 13})
        expect(self.page.locator('#like-status')).to_have_text('Liked!')
        expect(button).to_be_disabled()
        self.assertEqual(len(pending_hits), 1)

    def test_lost_like_response_reads_total_without_replaying_click(self):
        def lose_receipt(route):
            self.like_hits += 1
            self.like_total += 1
            route.abort()

        self.page.route('**/hit/*/likes', lose_receipt)
        self.page.goto(HOME)
        expect(self.page.locator('#like-count')).to_have_text('12')
        self.page.locator('#like-button').click()
        expect(self.page.locator('#like-status')).to_have_text('Couldn’t confirm your like.')
        expect(self.page.locator('#like-count')).to_have_text('13')
        self.assertEqual(self.like_hits, 1)

    def test_like_when_storage_blocked(self):
        self.page.add_init_script(
            "Object.defineProperty(window, 'localStorage', {get() {throw Error('blocked')}})"
        )
        self.page.goto(HOME)
        button = self.page.locator('#like-button')
        button.click()
        expect(self.page.locator('#like-count')).to_have_text('13')
        expect(button).to_be_disabled()
        self.assertEqual(self.like_hits, 1)


if __name__ == '__main__':
    unittest.main()

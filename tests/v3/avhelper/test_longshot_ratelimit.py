"""长图解析与限流守卫的单测：外部抓取全部用假 fetcher，不发真实请求。"""

import time


class TestLongshot:
    """projectjav 长图 URL 解析。"""

    SEARCH_HTML = """
    <div class="result">
      <a href="/movie/abcdef">IPZZ-961 某作品</a>
      <a href="/movie/zzzzzz">OTHER-001 别的作品</a>
    </div>
    """

    DETAIL_HTML = """
    <div class="gallery">
      <a href="https://images.projectjav.com/data/screenshots/234496.jpg"
         data-featherlight="image"><img src="thumb.jpg"></a>
    </div>
    """

    # 真实列表页结构：每个结果一张 video-item 卡片，卡片自带长图链接
    LIST_HTML = """
    <div class="col-md-4 mb-4 video-item" data-movie-id="1">
      <a href="/movie/other-001-1">OTHER-001 别的作品</a>
      <a href="https://images.projectjav.com/data/screenshots/other-001.jpg?v=1"
         data-featherlight="image">Screenshot</a>
    </div>
    <div class="col-md-4 mb-4 video-item" data-movie-id="2">
      <a href="/movie/ipzz-961-2">IPZZ-961 某作品</a>
      <a href="https://images.projectjav.com/data/screenshots/ipzz-961.jpg?v=2"
         data-featherlight="image">Screenshot</a>
    </div>
    """

    def test_norm_number(self, longshot_mod):
        assert longshot_mod.norm_number("IPZZ-961") == "ipzz961"
        assert longshot_mod.norm_number("ipzz 961") == "ipzz961"
        assert longshot_mod.norm_number(None) == ""

    def test_resolve_success(self, longshot_mod):
        calls = []

        def fetcher(url, referer):
            calls.append(url)
            return self.SEARCH_HTML if "searchTerm" in url else self.DETAIL_HTML

        url = longshot_mod.resolve_long("IPZZ-961", fetcher)
        assert url == "https://images.projectjav.com/data/screenshots/234496.jpg"
        assert any("searchTerm" in c for c in calls)
        assert any("/movie/abcdef" in c for c in calls)

    def test_resolve_skips_non_matching_movie(self, longshot_mod):
        """搜索页里没有番号匹配的详情链接时，不应误取别人的长图。"""
        def fetcher(url, referer):
            return "<a href='/movie/other'>NOPE-123 无关</a>"

        assert longshot_mod.resolve_long("IPZZ-961", fetcher) is None

    def test_resolve_handles_attribute_order(self, longshot_mod):
        """data-featherlight 在 href 之前也要能解析。"""
        html = "<a data-featherlight='image' href='https://x/y.jpg'>z</a>"

        def fetcher(url, referer):
            return self.SEARCH_HTML if "searchTerm" in url else html

        assert longshot_mod.resolve_long("IPZZ-961", fetcher) == "https://x/y.jpg"

    def test_resolve_returns_none_on_error(self, longshot_mod):
        def boom(url, referer):
            raise RuntimeError("站点挂了")

        assert longshot_mod.resolve_long("IPZZ-961", boom) is None

    def test_resolve_returns_none_when_page_missing(self, longshot_mod):
        assert longshot_mod.resolve_long("IPZZ-961", lambda u, r: None) is None
        assert longshot_mod.resolve_long("", lambda u, r: self.SEARCH_HTML) is None

    def test_resolve_from_list_card_without_detail_page(self, longshot_mod):
        """列表卡片自带长图链接时只抓一次，且必须取本番号卡片里那张（不跨卡片）。"""
        calls = []

        def fetcher(url, referer):
            calls.append(url)
            return self.LIST_HTML

        url = longshot_mod.resolve_long("IPZZ-961", fetcher)
        assert url == "https://images.projectjav.com/data/screenshots/ipzz-961.jpg?v=2"
        assert len(calls) == 1 and "searchTerm" in calls[0]

    def test_resolve_falls_back_to_detail_page(self, longshot_mod):
        """卡片里没有长图链接时仍走详情页（页面结构变化时的兜底）。"""
        calls = []

        def fetcher(url, referer):
            calls.append(url)
            if "searchTerm" in url:
                return ('<div class="col-md-4 video-item">'
                        '<a href="/movie/abcdef">IPZZ-961 某作品</a></div>')
            return self.DETAIL_HTML

        assert longshot_mod.resolve_long("IPZZ-961", fetcher) \
            == "https://images.projectjav.com/data/screenshots/234496.jpg"
        assert any("/movie/abcdef" in c for c in calls)


class FakeStore:
    """只实现限流需要的 kv 接口。"""

    def __init__(self):
        self.data = {}

    def kv_get(self, key, default=None):
        item = self.data.get(key)
        if not item:
            return default
        value, expires = item
        if expires and expires < time.time():
            return default
        return value

    def kv_set(self, key, value, ttl=0):
        self.data[key] = (value, time.time() + ttl if ttl else 0)


class TestRateLimit:
    """执行方案 §8.2 的限流参数不得放宽容。"""

    def test_first_check_allowed_then_interval_blocks(self, ratelimit_mod):
        limiter = ratelimit_mod.RateLimiter(FakeStore())
        allowed, why = limiter.check_allowed(max_per_day=6, min_interval_min=240)
        assert allowed and why == ""

        limiter.note_check()
        allowed, why = limiter.check_allowed(max_per_day=6, min_interval_min=240)
        assert allowed is False
        assert "240" in why and "还需" in why

    def test_daily_cap_blocks(self, ratelimit_mod):
        store = FakeStore()
        limiter = ratelimit_mod.RateLimiter(store)
        today = time.strftime("%Y-%m-%d")
        store.kv_set(f"subcheck:count:{today}", 6)
        allowed, why = limiter.check_allowed(max_per_day=6, min_interval_min=0)
        assert allowed is False and "上限" in why

    def test_note_check_counts_and_stamps(self, ratelimit_mod):
        store = FakeStore()
        limiter = ratelimit_mod.RateLimiter(store)
        limiter.note_check()
        limiter.note_check()
        today = time.strftime("%Y-%m-%d")
        assert store.kv_get(f"subcheck:count:{today}") == 2
        assert store.kv_get("subcheck:last") > 0

    def test_site_hourly_cap(self, ratelimit_mod):
        limiter = ratelimit_mod.RateLimiter(FakeStore())
        for _ in range(ratelimit_mod.SITE_HOURLY_MAX):
            assert limiter.site_available("馒头")[0] is True
            limiter.note_site_search("馒头")
        allowed, why = limiter.site_available("馒头")
        assert allowed is False and "上限" in why

    def test_site_cooldown_blocks_and_reports(self, ratelimit_mod):
        limiter = ratelimit_mod.RateLimiter(FakeStore())
        limiter.site_cooldown("馒头")
        allowed, why = limiter.site_available("馒头")
        assert allowed is False and "冷却" in why

    def test_antibot_detection(self, ratelimit_mod):
        assert ratelimit_mod.is_antibot_error("HTTP 403 Forbidden")
        assert ratelimit_mod.is_antibot_error("429 Too Many Requests")
        assert ratelimit_mod.is_antibot_error("请求过于频繁")
        assert not ratelimit_mod.is_antibot_error("connection reset by peer")

    def test_state_reports_today_count(self, ratelimit_mod):
        limiter = ratelimit_mod.RateLimiter(FakeStore())
        limiter.note_check()
        state = limiter.state()
        assert state["checked_today"] == 1
        assert state["site_hourly_max"] == ratelimit_mod.SITE_HOURLY_MAX

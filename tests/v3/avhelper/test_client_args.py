"""javdb 调用参数拼装的单测：只验证命令，不起子进程、不发网络请求。"""


class TestDetailArgs:
    """detail 的合并调用与 --id 捷径。"""

    def test_merges_magnets_and_uses_id(self, client_mod, monkeypatch):
        client = client_mod.JavdbClient()
        seen = {}

        def fake_run(key, args):
            seen["key"], seen["args"] = key, args
            return {"ok": True}

        monkeypatch.setattr(client, "_run", fake_run)
        assert client.detail("IPZZ-961", mid="kKr17e", with_magnets=True) == {"ok": True}
        # 一条命令取回详情+磁力，并用内部 id 省掉一次「番号→id」搜索
        assert seen["args"] == ["detail", "--id", "kKr17e", "--magnets"]
        # 失败计数/冷却仍按番号记账，不能换成 id
        assert seen["key"] == "detail:IPZZ-961"

    def test_falls_back_to_number(self, client_mod, monkeypatch):
        client = client_mod.JavdbClient()
        seen = {}
        monkeypatch.setattr(client, "_run", lambda key, args: seen.update(args=args) or {})
        client.detail("IPZZ-961")
        assert seen["args"] == ["detail", "IPZZ-961"]

    def test_magnets_command_unchanged(self, client_mod, monkeypatch):
        client = client_mod.JavdbClient()
        seen = {}
        monkeypatch.setattr(client, "_run", lambda key, args: seen.update(key=key, args=args) or {})
        client.magnets("IPZZ-961", cnsub=False)
        assert seen["args"] == ["magnets", "IPZZ-961"]
        assert seen["key"] == "magnets:IPZZ-961:False"

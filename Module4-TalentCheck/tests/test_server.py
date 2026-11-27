import json
import unittest
import urllib.error
import urllib.request

from tests.helpers import load_samples, make_service, offline_settings
from talent_check.server import create_server, start_in_thread


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings = offline_settings(cors_origins=["http://localhost:5173"])
        cls.server = create_server(settings, make_service(), host="127.0.0.1", port=0)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        start_in_thread(cls.server)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, method, path, body=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        h = {"Content-Type": "application/json", **(headers or {})}
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read() or b"{}"), r.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), e.headers

    def test_root_lists_endpoints(self):
        s, b, _ = self.call("GET", "/")
        self.assertEqual((s, b["status"]), (200, "running"))
        self.assertIn("POST /api/talent-check", b["endpoints"])

    def test_health_and_companies(self):
        s, b, _ = self.call("GET", "/health")
        self.assertEqual((s, b["status"], b["companies"]), (200, "ok", 116))
        s, b, _ = self.call("GET", "/api/companies?q=oracle")
        self.assertEqual(len(b["companies"]), 2)
        s, b, _ = self.call("GET", "/api/companies/4")
        self.assertEqual(b["requirements"]["DSA"], {"level": 9, "bloom": "CR"})
        self.assertEqual(self.call("GET", "/api/companies/99999")[0], 404)
        self.assertEqual(self.call("GET", "/api/companies?limit=abc")[0], 400)
        self.assertEqual(self.call("GET", "/nope")[0], 404)

    def test_talent_check_ok(self):
        p = load_samples()["Rohan"]
        s, b, h = self.call("POST", "/api/talent-check", {"profile": p, "company": "Google"},
                            headers={"Origin": "http://localhost:5173"})
        self.assertEqual(s, 200)
        self.assertEqual(len(b["skillset_gap"]), 12)
        self.assertEqual(h["Access-Control-Allow-Origin"], "http://localhost:5173")
        s, b, _ = self.call("POST", "/api/talent-check", {"profile": p, "company_id": 78})
        self.assertEqual(b["company"], "Microsoft Corporation")

    def test_cors_blocks_unknown_origin_and_preflight(self):
        _, _, h = self.call("GET", "/health", headers={"Origin": "http://evil.example"})
        self.assertIsNone(h.get("Access-Control-Allow-Origin"))
        req = urllib.request.Request(self.base + "/api/talent-check", method="OPTIONS",
                                     headers={"Origin": "http://localhost:5173"})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.status, 204)
            self.assertIn("POST", r.headers["Access-Control-Allow-Methods"])

    def test_error_mapping(self):
        p = load_samples()["Rohan"]
        s, b, _ = self.call("POST", "/api/talent-check", {"profile": p, "company": "Oracle"})
        self.assertEqual((s, b["error"]["code"]), (409, "ambiguous_company"))
        self.assertEqual(len(b["error"]["details"]), 2)
        s, b, _ = self.call("POST", "/api/talent-check", {"profile": p, "company": "Nope"})
        self.assertEqual((s, b["error"]["code"]), (404, "company_not_found"))
        s, b, _ = self.call("POST", "/api/talent-check", {"profile": {"name": "x"}, "company": "Google"})
        self.assertEqual((s, b["error"]["code"]), (422, "invalid_profile"))
        s, b, _ = self.call("POST", "/api/talent-check", {"company": "Google"})
        self.assertEqual(s, 400)
        s, b, _ = self.call("POST", "/api/talent-check", raw=b"{broken")
        self.assertEqual(s, 400)
        s, b, _ = self.call("POST", "/api/talent-check", raw=b"[1,2]")
        self.assertEqual(s, 400)
        s, b, _ = self.call("POST", "/api/talent-check", raw=b"")
        self.assertEqual(s, 400)
        s, b, _ = self.call("POST", "/api/talent-check", {"profile": p, "company": ""})
        self.assertEqual(s, 404)
        s, b, _ = self.call("POST", "/api/other", {"x": 1})
        self.assertEqual(s, 404)

    def test_body_too_large(self):
        try:
            s, b, _ = self.call("POST", "/api/talent-check", raw=b'{"profile":"' + b"a" * 1_100_000 + b'"}')
            self.assertEqual(s, 413)
        except urllib.error.URLError:
            pass   # server closed the connection before the client finished uploading - also a rejection


if __name__ == "__main__":
    unittest.main()

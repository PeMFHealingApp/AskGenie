import unittest
from unittest.mock import patch

from starlette.testclient import TestClient

import api
from mcp_server import asgi_app, validate_program_url, verify_program_link


class CatalogTests(unittest.TestCase):
    def test_exact_program_is_first_and_url_is_unchanged(self):
        results = api.search_catalog("Collagen Building")
        self.assertEqual(results[0]["Program Title"], "Collagen Building")
        original = next(p for p in api.programs if p["Program Title"] == "Collagen Building")
        self.assertEqual(results[0]["Full URL"], original["Full URL"])

    def test_vascular_flow_excludes_unrelated_flow_programs(self):
        results = api.search_catalog("vascular flow")
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["Program Title"].startswith("Vascular Flow & Endothelial Support"))

    def test_original_categories_are_returned_and_searchable(self):
        results = api.search_catalog("kidney", category="12-meridian-spectrum")
        self.assertTrue(results)
        for result in results:
            self.assertIn("12-meridian-spectrum", result["Categories"])
            self.assertTrue(result["Category"])

    def test_supporting_category_filters_retain_the_topic(self):
        results = api.search_catalog("collagen", category="amino-acid")
        self.assertEqual({p["Program Title"].split()[0] for p in results}, {"Lysine", "Threonine"})
        self.assertEqual(results, api.search_catalog("collagen amino acids"))

    def test_backpain_alias_finds_direct_program(self):
        self.assertEqual(api.search_catalog("backpain")[0]["Program Title"], "Back Pain Energetics")

    def test_no_match_and_blank_queries_remain_empty(self):
        for query in ["", "   ", "!!!", "unfindableprogramxyz", "collagen unfindableprogramxyz"]:
            self.assertEqual(api.search_catalog(query), [])

    def test_catalog_urls_are_never_synthesized_or_duplicated(self):
        original_urls = {p["Full URL"] for p in api.programs}
        for query in ["spine", "heart", "collagen", "vascular flow", "backpain"]:
            urls = [p["Full URL"] for p in api.search_catalog(query)]
            self.assertEqual(len(urls), len(set(urls)))
            self.assertTrue(set(urls).issubset(original_urls))

    def test_legacy_editor_records_are_supported(self):
        record = api.normalize_program({"title": "Example", "url": "https://www.epemf.app/example", "category": "body-repair, pain"})
        self.assertEqual(record["Categories"], ["body-repair", "pain"])
        self.assertEqual(record["Program Title"], "Example")

    def test_stats_reflect_the_catalog(self):
        stats = api.catalog_stats()
        self.assertEqual(stats["program_count"], len(api.programs))
        self.assertIn("amino-acid", stats["categories"])

    def test_rest_response_remains_an_array(self):
        with api.app.test_client() as client:
            results = client.get("/programs?q=collagen&limit=1").get_json()
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["Categories"])
            self.assertEqual(client.get("/programs?limit=bogus").status_code, 400)
            self.assertEqual(client.get("/programs?limit=0").status_code, 400)


class MCPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(asgi_app, base_url="http://localhost:5000")
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)

    def setUp(self):
        self.headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"}

    def rpc(self, method, params=None):
        return self.client.post("/mcp/", headers=self.headers, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})

    def test_initialization_and_tools(self):
        result = self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "tests", "version": "1"}})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["result"]["protocolVersion"], "2025-06-18")
        tools = self.rpc("tools/list").json()["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, {"search_programs", "get_catalog_stats", "verify_program_link"})
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools))

    def test_mcp_search_and_count(self):
        result = self.rpc("tools/call", {"name": "search_programs", "arguments": {"query": "vascular flow"}}).json()["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["total_matches"], 1)
        count = self.rpc("tools/call", {"name": "get_catalog_stats", "arguments": {}}).json()["result"]
        self.assertEqual(count["structuredContent"]["program_count"], len(api.programs))

    def test_invalid_tool_arguments_are_errors(self):
        for arguments in [{"query": "collagen", "limit": 0}, {"query": ""}, {"query": "   "}]:
            result = self.rpc("tools/call", {"name": "search_programs", "arguments": arguments}).json()["result"]
            self.assertTrue(result["isError"])

    def test_untrusted_host_and_origin_are_rejected(self):
        response = self.client.post("/mcp/", headers={**self.headers, "Host": "evil.example"}, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assertEqual(response.status_code, 421)
        response = self.client.post("/mcp/", headers={**self.headers, "Origin": "https://evil.example"}, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assertEqual(response.status_code, 403)

    def test_link_verification_never_fetches_arbitrary_urls(self):
        with patch("urllib.request.build_opener") as opener:
            with self.assertRaises(ValueError):
                verify_program_link("http://127.0.0.1/private")
            opener.assert_not_called()
        for url in ["https://evil.example/x", "https://www.epemf.app:8443/x", "http://www.epemf.app/x", "https://user:password@www.epemf.app/x"]:
            with self.assertRaises(ValueError):
                validate_program_url(url)

    def test_legacy_rest_routes_work_under_asgi(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        result = self.client.get("/programs?q=vascular%20flow").json()
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()

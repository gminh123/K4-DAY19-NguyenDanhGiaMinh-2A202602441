"""Knowledge Graph contract tests — offline (no Neo4j, no API key), independent of your ontology.

    pytest tests/test_graph.py -v

build_graph (KG-2) and Neo4jGraph.context (KG-3) depend on your ontology, so they are checked by
`python bench_kg.py --check` against a real Neo4j instead.
"""

import importlib
import os
import unittest

PACKAGE_NAME = os.getenv("LAB_SOLUTION_PACKAGE", "src")
graph = importlib.import_module(f"{PACKAGE_NAME}.graph")
package = importlib.import_module(PACKAGE_NAME)

CRIMES = ["mua bán trái phép chất ma túy", "vận chuyển trái phép chất ma túy", "tổ chức sử dụng trái phép chất ma túy"]

class TestLinkEntity(unittest.TestCase):
    def test_exact_after_normalize(self):
        self.assertEqual(graph.link_entity("Tội Mua bán trái phép chất ma túy", CRIMES), CRIMES[0])

    def test_fuzzy_spelling_variant(self):
        # "ma tuý" (accent on y) vs "ma túy" — common in Vietnamese news
        self.assertEqual(graph.link_entity("vận chuyển trái phép chất ma tuý", CRIMES), CRIMES[1])

    def test_returns_original_spelling_from_known(self):
        known = ["Mua bán trái phép chất ma túy"]
        self.assertEqual(graph.link_entity("mua bán trái phép chất ma túy", known), known[0])

    def test_unrelated_name_is_none(self):
        self.assertIsNone(graph.link_entity("lừa đảo chiếm đoạt tài sản", CRIMES))

    def test_empty_is_none(self):
        self.assertIsNone(graph.link_entity("", CRIMES))

class TestGraphRAGAgent(unittest.TestCase):
    def setUp(self):
        self.store = package.EmbeddingStore("kg_agent_test")
        self.store.add_documents([package.Document("news-1", "Lê Minh Thành bị tuyên 36 tháng tù.", {"doc_id": "news-1"})])

        class FakeGraph:
            def context(self, question, doc_ids):
                self.doc_ids = doc_ids
                return ["[Điều 251 BLHS - Tội mua bán trái phép chất ma túy] khoản 1: phạt tù từ 02 năm đến 07 năm"]

        self.fake = FakeGraph()
        self.agent = graph.GraphRAGAgent(store=self.store, graph=self.fake, llm_fn=lambda prompt: prompt)

    def test_passes_doc_ids_of_retrieved_chunks(self):
        self.agent.answer("Lê Minh Thành bị xử theo điều nào?", top_k=1)
        self.assertEqual(list(self.fake.doc_ids), ["news-1"])

    def test_prompt_has_graph_facts_chunks_and_question(self):
        prompt = self.agent.answer("Lê Minh Thành bị xử theo điều nào?", top_k=1)
        self.assertIn("- [Điều 251 BLHS", prompt)
        self.assertIn("36 tháng", prompt)
        self.assertIn("[1] Lê Minh Thành bị tuyên 36 tháng tù.", prompt)
        self.assertIn("Lê Minh Thành bị xử theo điều nào?", prompt)

    def test_deduplicates_doc_ids_and_formats_multiple_chunks(self):
        self.store.search = lambda question, top_k: [
            {"content": "Chunk A", "metadata": {"doc_id": "news-1"}},
            {"content": "Chunk B", "metadata": {"doc_id": "news-1"}},
            {"content": "Chunk C", "metadata": {"doc_id": "news-2"}},
        ]
        prompt = self.agent.answer("câu hỏi", top_k=3)
        self.assertEqual(self.fake.doc_ids, ["news-1", "news-2"])
        self.assertIn("[1] Chunk A\n\n[2] Chunk B\n\n[3] Chunk C", prompt)
        self.assertIn("- [Điều 251 BLHS", prompt)

class TestNeo4jGraphContext(unittest.TestCase):
    def setUp(self):
        self.graph = object.__new__(graph.Neo4jGraph)
        self.graph.seed_facts = lambda question, doc_ids, limit=60: (
            ["case-id"], ["(Person: Lê Minh Thành) -[INVOLVED_IN]-> (Case: vụ Thành)"])

        def run(cypher, **params):
            if "RETURN elementId(k) AS id" in cypher:
                return [{"id": "case-id", "name": "vụ Thành", "summary": "Lê Minh Thành bị tuyên 36 tháng tù."}]
            if "case_ids" in params:
                return [{
                    "article_id": "Điều 251 BLHS", "title": "Tội mua bán trái phép chất ma túy",
                    "number": 1, "text": "Phạt tù từ 02 năm đến 07 năm.", "penalty": "phạt tù từ 02 năm đến 07 năm",
                }]
            return [{
                "article_id": "Điều 255 BLHS", "title": "Tội tổ chức sử dụng trái phép chất ma túy",
                "number": 4, "text": "Phạt tù 20 năm hoặc tù chung thân.", "penalty": "phạt tù 20 năm hoặc tù chung thân",
            }]

        self.graph.run = run

    def test_expands_case_to_legal_basis(self):
        facts = self.graph.context("Lê Minh Thành bị tuyên bao nhiêu tháng tù?", ["news-1"])
        self.assertTrue(any("36 tháng tù" in fact for fact in facts))
        self.assertTrue(any("Điều 251 BLHS" in fact and "02 năm đến 07 năm" in fact for fact in facts))

    def test_includes_max_clause_for_named_article_question(self):
        facts = self.graph.context("Hoàng Nato bị bắt theo Điều 255, tối đa bao nhiêu?", ["news-2"])
        self.assertTrue(any("Điều 255 BLHS" in fact and "tù chung thân" in fact for fact in facts))

if __name__ == "__main__":
    unittest.main()

import unittest

from ordo.introspection import describe_system
from ordo.introspection.registry import PUBLISHED_INTROSPECTION_SECTIONS


class IntrospectionEnforcementTest(unittest.TestCase):
    def test_root_sections_match_covered_published_registry(self) -> None:
        payload = describe_system()

        covered_sections = {section.name for section in PUBLISHED_INTROSPECTION_SECTIONS}
        self.assertEqual(set(payload["sections"]) - {"discovery"}, covered_sections)

    def test_discovery_sections_match_covered_published_registry(self) -> None:
        payload = describe_system()

        discovery_sections = payload["sections"]["discovery"]["sections"]
        covered_producers = {section.name: section.producer_name for section in PUBLISHED_INTROSPECTION_SECTIONS}
        self.assertEqual(set(discovery_sections), set(covered_producers))
        for name, producer_name in covered_producers.items():
            self.assertEqual(discovery_sections[name]["producer"], producer_name)
            self.assertTrue(discovery_sections[name]["published"])


if __name__ == "__main__":
    unittest.main()

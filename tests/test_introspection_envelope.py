import unittest

from ordo.introspection import INTROSPECTION_VERSION, build_introspection_envelope


class IntrospectionEnvelopeTest(unittest.TestCase):
    def test_builds_shared_versioned_envelope(self) -> None:
        envelope = build_introspection_envelope(
            sections={
                "operations": {"connectors": []},
                "capabilities": {"items": []},
            }
        )

        self.assertEqual(envelope["introspection_version"], INTROSPECTION_VERSION)
        self.assertEqual(
            envelope["sections"],
            {
                "operations": {"connectors": []},
                "capabilities": {"items": []},
            },
        )

    def test_defaults_sections_to_empty_object(self) -> None:
        envelope = build_introspection_envelope()

        self.assertEqual(envelope, {"introspection_version": INTROSPECTION_VERSION, "sections": {}})


if __name__ == "__main__":
    unittest.main()

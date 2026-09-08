"""Every example-related topic must have a generated documentation page."""

from ordo.model.examples_catalog import EXAMPLES_CATALOG
from tools.build_help_site_docs import STATIC_TOPICS


def test_example_related_topics_are_generated():
    referenced = {
        topic
        for example in EXAMPLES_CATALOG["examples"]
        for topic in example.get("related_topics", [])
    }
    assert referenced <= set(STATIC_TOPICS)
    assert "features" in referenced

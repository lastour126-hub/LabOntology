from __future__ import annotations


def test_graph_schema_and_creator_modules_follow_their_responsibilities():
    from core import graph, schema
    from core.creator import bundle, discovery

    assert callable(graph.load_graph)
    assert callable(graph.validate)
    assert callable(schema.load_schema)
    assert callable(discovery.discover_skill)
    assert callable(discovery.discover_tree)
    assert callable(bundle.export_bundle)

    assert not hasattr(discovery, "export_bundle")
    assert not hasattr(bundle, "discover_skill")

from core.runtime.models import SkillFlow, FlowNode, SkillSpec


def test_flow_node_round_trips_from_dict():
    node = FlowNode.from_dict({
        "id": "node:parse",
        "type": "skill_call",
        "skill": "skill:parser",
        "order": 1,
        "outputs": ["artifact:constraints"],
    })

    assert node.id == "node:parse"
    assert node.skill_id == "skill:parser"
    assert node.output_artifacts == ["artifact:constraints"]


def test_skill_flow_loads_ordered_nodes():
    flow = SkillFlow.from_dict({
        "id": "flow:test",
        "nodes": [
            {"id": "node:b", "type": "skill_call", "order": 2},
            {"id": "node:a", "type": "skill_call", "order": 1},
        ],
    })

    assert [node.id for node in flow.nodes] == ["node:a", "node:b"]

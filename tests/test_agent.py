"""Agent loop, trace labelling and provenance."""

from __future__ import annotations

from agentfw.agent.loop import run_episode
from agentfw.agent.providers.anthropic import to_anthropic
from agentfw.agent.providers.scripted import ScriptedClient, call, say
from agentfw.agent.trace import Trace
from agentfw.core.types import Integrity
from agentfw.sandbox.registry import ToolRouter, load_all
from agentfw.sandbox.world import World


def _episode(steps, tools, utterance="do the thing"):
    load_all()
    world = World.from_fixture("office_baseline")
    router = ToolRouter.for_tools(world, tools)
    ep = run_episode(
        client=ScriptedClient(steps), world=world, router=router, utterance=utterance
    )
    return ep, world


def test_loop_records_labeled_spans_in_order() -> None:
    ep, _world = _episode(
        [
            call("email_list", {"folder": "inbox"}),
            call("email_read", {"id": "m-001"}, cid="c2"),
            say("Summarised."),
        ],
        ["email_list", "email_read"],
    )
    kinds = [s.kind for s in ep.trace.spans]
    assert kinds[0] == "system_prompt"
    assert kinds[1] == "user_turn"
    assert kinds.count("agent_tool_call") == 2
    assert kinds.count("tool_result") == 2
    by_kind = {s.kind: s for s in ep.trace.spans}
    assert by_kind["system_prompt"].label.integrity is Integrity.SYSTEM
    assert by_kind["user_turn"].label.integrity is Integrity.USER
    email_span = next(
        s for s in ep.trace.spans if s.kind == "tool_result" and s.tool_name == "email_read"
    )
    assert email_span.label.integrity is Integrity.UNTRUSTED_EMAIL
    assert ep.final_text == "Summarised."
    assert ep.stop_reason == "stop"


def test_context_label_degrades_once_untrusted_content_is_read() -> None:
    trace = Trace()
    trace.system("s")
    trace.user("u")
    assert trace.context_label().integrity is Integrity.USER
    # after a web fetch the whole context is conservatively untrusted
    ep, _ = _episode(
        [
            call("web_fetch", {"url": "https://cloudhost.example/pricing"}),
            say("done"),
        ],
        ["web_fetch"],
    )
    assert ep.trace.context_label().integrity is Integrity.UNTRUSTED_WEB


def test_literal_evidence_links_arguments_back_to_their_source_span() -> None:
    ep, _world = _episode(
        [
            call("web_fetch", {"url": "https://cloudhost.example/pricing"}),
            call(
                "web_post",
                {"url": "https://x.example", "data": "Large instance: 88 USD/month."},
                cid="c2",
            ),
            say("done"),
        ],
        ["web_fetch", "web_post"],
    )
    post_call = next(
        s for s in ep.trace.spans if s.kind == "agent_tool_call" and s.tool_name == "web_post"
    )
    assert post_call.derived_from, "argument copied from a fetched page has no evidence link"
    source = {s.id: s for s in ep.trace.spans}[post_call.derived_from[0]]
    assert source.tool_name == "web_fetch"


def test_tool_error_does_not_end_the_episode() -> None:
    ep, _world = _episode(
        [
            call("files_read", {"path": "does/not/exist.md"}),
            call("files_read", {"path": "reports/q4-2025-final.md"}, cid="c2"),
            say("ok"),
        ],
        ["files_read"],
    )
    assert [c["ok"] for c in ep.tool_calls] == [False, True]
    assert ep.stop_reason == "stop"


def test_max_steps_stops_a_looping_agent() -> None:
    steps = [call("files_list", {}, cid=f"c{i}") for i in range(20)]
    load_all()
    world = World.from_fixture("office_baseline")
    router = ToolRouter.for_tools(world, ["files_list"])
    ep = run_episode(
        client=ScriptedClient(steps),
        world=world,
        router=router,
        utterance="loop",
        max_steps=4,
    )
    assert ep.steps == 4
    assert ep.stop_reason == "max_steps"


def test_provider_error_is_recorded_not_raised() -> None:
    class Boom:
        name = "boom"

        def complete(self, messages, tools):
            raise RuntimeError("upstream 500")

    load_all()
    world = World.from_fixture("office_baseline")
    router = ToolRouter.for_tools(world, ["files_list"])
    ep = run_episode(client=Boom(), world=world, router=router, utterance="x")
    assert ep.stop_reason == "provider_error"
    assert ep.error is not None and "upstream 500" in ep.error


def test_anthropic_message_translation() -> None:
    system, msgs = to_anthropic(
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "thinking",
                "tool_calls": [
                    {
                        "id": "t1",
                        "type": "function",
                        "function": {"name": "files_list", "arguments": '{"pattern": "*"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "t1", "content": "a.md"},
        ]
    )
    assert system == "sys"
    assert msgs[0]["role"] == "user"
    assert msgs[1]["content"][1]["type"] == "tool_use"
    assert msgs[1]["content"][1]["input"] == {"pattern": "*"}
    assert msgs[2]["content"][0]["type"] == "tool_result"

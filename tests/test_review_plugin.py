import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = ROOT / ".opencode" / "plugin" / "fifth-pick-review-adapter.ts"
COMMAND_PATH = ROOT / ".opencode" / "commands" / "fifth-pick-review.md"
ASSURANCE_PATH = ROOT / "docs" / "fifth-pick" / "assurance.md"


class ReviewPluginContractTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the adapter hooks")
    def test_cli_quoted_review_envelope_marks_and_correlates_native_subtask(self) -> None:
        script = r"""
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";

const { FifthPickReviewAdapter } = await import(pathToFileURL(process.argv[1]));
const hooks = await FifthPickReviewAdapter({ directory: process.cwd() });
const review_material = 'Synthetic evidence with "quotes" and a \\ backslash.';
const digest = createHash("sha256").update(review_material).digest("hex");
const envelope = JSON.stringify({
    schema_version: 1,
    run_id: "m10-hook-regression",
    subject: "native subtask",
    initial_artifact_sha256: digest,
    current_artifact_sha256: digest,
    revision: 0,
    review_material,
});
const sessionID = "parent-session";
const cliQuote = (arg) => '"' + arg.replaceAll('"', '\\"') + '"';
for (const [args, expected] of [
    [envelope.replace('"revision":0', '"revision":1,"revision":0'), false],
    [cliQuote(envelope.replace('"revision":0', '"rev\\u0069sion":1,"revision":0')), false],
    [cliQuote(cliQuote(envelope)), false],
    [cliQuote(envelope.replace(digest, "0".repeat(64))), false],
    [envelope, true],
    [cliQuote(envelope), true],
]) {
    const part = {
        type: "subtask", prompt: "Expanded review prompt", description: "Independent review",
    };
    const textPart = { type: "text", text: "Other content" };
    await hooks["command.execute.before"](
        { command: "fifth-pick-review", sessionID, arguments: args },
        { parts: [textPart, part] },
    );
    assert.equal(part.prompt, "Expanded review prompt");
    assert.equal(textPart.text, "Other content");
    assert.equal(part.description.includes("FIFTH_PICK_REVIEW_TASK="), expected);
    if (!expected) continue;

    const input = { tool: "task", sessionID, callID: "native-part-id" };
    const argsForTask = {
        subagent_type: "fifth-pick-reviewer", prompt: part.prompt, description: part.description,
    };
    const original = "<task_result>Uncorrelated result</task_result>";
    const result = { output: original, metadata: {} };
    await hooks["tool.execute.before"](input, {
        args: { ...argsForTask, prompt: part.description, description: "Missing marker" },
    });
    await hooks["tool.execute.after"]({ ...input, args: argsForTask }, result);
    assert.equal(result.output, original);

    await hooks["tool.execute.before"](input, { args: argsForTask });
    await hooks["tool.execute.after"](
        { ...input, callID: "other-part-id", args: argsForTask }, result,
    );
    assert.equal(result.output, original);
    await hooks["tool.execute.after"]({ ...input, args: argsForTask }, result);
    assert.match(result.output, /STOPPED; task result envelope correlation failed/);
}
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(PLUGIN_PATH)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_plugin_registers_only_lifecycle_and_tool_observers(self) -> None:
        source = PLUGIN_PATH.read_text(encoding="utf-8")

        self.assertIn('import type { Plugin } from "@opencode-ai/plugin"', source)
        self.assertIn('"command.execute.before"', source)
        self.assertIn('"tool.execute.before"', source)
        self.assertIn('"tool.execute.after"', source)
        self.assertNotIn('"permission.ask"', source)
        self.assertNotIn("output.status", source)

    @unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the adapter hooks")
    def test_dispatch_cli_envelopes_are_validated_before_bridge_invocation(self) -> None:
        script = r"""
import assert from "node:assert/strict";
import childProcess from "node:child_process";
import { createHash } from "node:crypto";
import { EventEmitter } from "node:events";
import { syncBuiltinESMExports } from "node:module";
import { pathToFileURL } from "node:url";

const requests = [];
const cycleFor = ({ initial_artifact_sha256, run_id, subject }) =>
    "review-" + createHash("sha256")
        .update(JSON.stringify({ initial_artifact_sha256, run_id, subject })).digest("hex");
let mode = "fresh";
childProcess.spawn = () => {
    if (mode === "spawn") throw new Error("spawn unavailable");
    const child = new EventEmitter();
    child.kill = () => {};
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    child.stderr.resume = () => {};
    child.stdin = new EventEmitter();
    child.stdin.end = (raw) => {
        if (mode === "write") throw new Error("synchronous write failure");
        const request = JSON.parse(raw);
        requests.push(request);
        const cycle = cycleFor(request);
        const key = cycle + "-02-revision_attempt";
        const otherCycle = cycleFor({ ...request, run_id: "different-run" });
        const otherKey = otherCycle + "-02-revision_attempt";
        const stopped = mode === "replay";
        const response = {
            review_cycle_id: mode === "other-run" ? otherCycle : cycle,
            state: stopped ? "STOPPED" : "REVISION_REQUIRED",
            correction_count: 1,
            correction_available: false,
            receipt_event_keys: {
                "other-run": [otherKey],
                "other-key": [otherKey],
                "suffix": ["garbage-02-revision_attempt"],
                "extra-key": [key, otherKey],
                "replay": [],
            }[mode] ?? [key],
        };
        queueMicrotask(() => {
            if (mode === "stdin") child.stdin.emit("error", new Error("EPIPE"));
            if (mode === "stdout") child.stdout.emit("error", new Error("broken stdout"));
            if (mode === "stderr") child.stderr.emit("error", new Error("broken stderr"));
            if (mode === "process") child.emit("error", new Error("ENOENT"));
            const json = JSON.stringify(response);
            const output = mode === "malformed" ? "{" : mode === "duplicate-response"
                ? json.replace('"correction_count":1', '"correction_count":0,"correction_count":1')
                : json;
            child.stdout.emit("data", Buffer.from(output + "\n"));
            child.emit("close", mode === "signal" ? null : stopped ? 2 : 0);
        });
    };
    return child;
};
syncBuiltinESMExports();
const { FifthPickReviewAdapter } = await import(pathToFileURL(process.argv[1]));
const hooks = await FifthPickReviewAdapter({ directory: process.cwd() });
const hook = hooks["command.execute.before"];
const data = {
    schema_version: 1, run_id: "m10-dispatch", subject: 'Subject with "quotes" and a \\ backslash',
    initial_artifact_sha256: "a".repeat(64), current_artifact_sha256: "a".repeat(64), revision: 1,
};
const cliQuote = (arg) => '"' + arg.replaceAll('"', '\\"') + '"';
async function dispatch(args) {
    const part = { type: "text", text: "Dispatch request" };
    await hook(
        { command: "fifth-pick-review-dispatch", sessionID: "parent", arguments: args },
        { parts: [part] },
    );
    return JSON.parse(part.text);
}
for (const invalid of [
    "{", cliQuote("{"), cliQuote(cliQuote(JSON.stringify(data))),
    JSON.stringify(data).replace('"revision":1', '"revision":0,"revision":1'),
    cliQuote(JSON.stringify(data).replace('"revision":1', '"rev\\u0069sion":0,"revision":1')),
    JSON.stringify({ ...data, revision: 0 }),
    cliQuote(JSON.stringify({ ...data, current_artifact_sha256: "invalid" })),
    JSON.stringify({ ...data, review_material: "unexpected" }),
]) {
    assert.equal((await dispatch(invalid)).reason, "INVALID_DISPATCH_ENVELOPE");
}
assert.deepEqual(requests, []);
const raw = await dispatch(JSON.stringify(data));
assert.equal(raw.controller_instruction, "dispatch the single Builder correction now");
mode = "replay";
const wrapped = await dispatch(cliQuote(JSON.stringify(data)));
assert.equal(wrapped.state, "STOPPED");
assert.match(wrapped.controller_instruction, /^do not dispatch Builder/);
assert.deepEqual(requests, Array(2).fill({ ...data, kind: "REVISION_DISPATCHED" }));

for (mode of ["other-run", "other-key", "suffix", "extra-key"]) {
    const result = await dispatch(JSON.stringify(data));
    assert.equal(result.state, "STOPPED", mode);
    assert.deepEqual(result.receipt_event_keys, [], mode);
    assert.match(result.controller_instruction, /^do not dispatch Builder/);
}
for (mode of [
    "stdin", "write", "stdout", "stderr", "process", "spawn", "signal", "malformed",
    "duplicate-response",
]) {
    const result = await dispatch(JSON.stringify(data));
    assert.equal(result.state, "STOPPED", mode);
    assert.equal(result.reason, "REVISION_RECEIPT_UNAVAILABLE", mode);
    assert.deepEqual(result.receipt_event_keys, [], mode);
}

mode = "stdin";
const material = 'Literal JSON-like content: "revision":1, "revision":0';
const digest = createHash("sha256").update(material).digest("hex");
const review = {
    ...data, revision: 0, review_material: material,
    initial_artifact_sha256: digest, current_artifact_sha256: digest,
};
const part = { type: "subtask", description: "Independent review", prompt: material };
const reviewArgument = cliQuote(JSON.stringify(review));
await hook(
    { command: "fifth-pick-review", sessionID: "parent", arguments: reviewArgument },
    { parts: [part] },
);
const input = { tool: "task", sessionID: "parent", callID: "task-part" };
const args = { subagent_type: "fifth-pick-reviewer", description: part.description };
const output = {
    metadata: { sessionId: "reviewer-session" },
    output: '<task id="reviewer-session" state="completed"><task_result>{}</task_result></task>',
};
await hooks["tool.execute.before"](input, { args });
await hooks["tool.execute.after"]({ ...input, args }, output);
const reviewStop = JSON.parse(output.output.split("Fifth Pick review controller response: ")[1]);
assert.equal(reviewStop.state, "STOPPED");
assert.equal(reviewStop.reason, "VERDICT_TRANSPORT_UNAVAILABLE");
assert.deepEqual(reviewStop.receipt_event_keys, []);
const before = requests.length;
const warnings = [];
console.warn = (line) => warnings.push(line);
await hook(
    { command: "fifth-pick-review-dispatch", sessionID: "parent", arguments: JSON.stringify(data) },
    { parts: [] },
);
assert.equal(requests.length, before);
assert.match(warnings.join("\n"), /no controller response channel/i);
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, str(PLUGIN_PATH)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bridge_invocation_uses_fixed_argument_vector_without_shell(self) -> None:
        source = PLUGIN_PATH.read_text(encoding="utf-8")

        self.assertRegex(source, re.compile(r'spawn\(\s*"uv"'))
        self.assertIn('"run", "--no-sync", "python", "-m", "fifth_pick.review_bridge"', source)
        self.assertIn("shell: false", source)
        self.assertNotIn("input.$", source)
        self.assertNotIn("Bun.$", source)

    def test_adapter_is_bound_to_exact_review_command_and_named_agents(self) -> None:
        source = PLUGIN_PATH.read_text(encoding="utf-8")

        self.assertIn('const REVIEW_COMMAND = "fifth-pick-review"', source)
        self.assertIn('"fifth-pick-reviewer"', source)
        self.assertIn("review_cycle_id", source)

    def test_review_digest_binds_exact_material_before_bridge_transport(self) -> None:
        source = PLUGIN_PATH.read_text(encoding="utf-8")

        self.assertIn('createHash("sha256")', source)
        self.assertIn('Buffer.from(data.review_material, "utf8")', source)
        self.assertIn("data.current_artifact_sha256 !== materialDigest", source)
        self.assertIn(
            "data.revision === 0 && data.initial_artifact_sha256 !== materialDigest", source
        )

    def test_reviewer_result_is_correlated_by_exact_task_call_id(self) -> None:
        source = PLUGIN_PATH.read_text(encoding="utf-8")

        self.assertIn("reviewerCallID", source)
        self.assertIn("invocationID", source)
        self.assertIn("input.callID", source)
        self.assertIn("context.reviewerCallID !== input.callID", source)

    def test_controller_dispatch_command_requires_confirmed_receipt(self) -> None:
        source = PLUGIN_PATH.read_text(encoding="utf-8")
        command = (ROOT / ".opencode" / "commands" / "fifth-pick-review-dispatch.md").read_text(
            encoding="utf-8"
        )

        self.assertIn('const REVIEW_DISPATCH_COMMAND = "fifth-pick-review-dispatch"', source)
        self.assertIn("input.command === REVIEW_DISPATCH_COMMAND", source)
        self.assertIn("REVISION_DISPATCHED", source)
        self.assertIn("before dispatching the builder", command.lower())
        self.assertIn("do not dispatch the builder", command.lower())
        self.assertIn('expectedCycle + "-02-revision_attempt"', source)
        self.assertNotIn('"fifth-pick-builder"', source)

    def test_review_command_documents_strict_transport_envelope(self) -> None:
        text = COMMAND_PATH.read_text(encoding="utf-8")

        for field in (
            "schema_version",
            "run_id",
            "subject",
            "initial_artifact_sha256",
            "current_artifact_sha256",
            "revision",
            "review_material",
        ):
            with self.subTest(field=field):
                self.assertIn(field, text)
        self.assertIn("metadata is not review evidence", text.lower())

    def test_review_command_uses_v11820_subtask_frontmatter(self) -> None:
        text = COMMAND_PATH.read_text(encoding="utf-8")
        frontmatter = text.split("---", maxsplit=2)[1]

        self.assertIn("subtask: true", frontmatter)
        self.assertNotIn("subagent:", frontmatter)

    def test_inline_review_command_distinguishes_command_from_skill(self) -> None:
        command = COMMAND_PATH.read_text(encoding="utf-8")

        self.assertIn("slash command, not a skill", command)
        self.assertIn(
            "use only the supplied inline evidence and return the verdict directly", command
        )
        self.assertIn("Do not call the skill tool", command)

    def test_review_command_does_not_reference_invocation_marker(self) -> None:
        command = COMMAND_PATH.read_text(encoding="utf-8")

        self.assertNotIn("FIFTH_PICK_REVIEW_TASK", command)

    def test_completed_task_envelope_session_matches_task_metadata(self) -> None:
        source = PLUGIN_PATH.read_text(encoding="utf-8")

        self.assertIn("taskResultSessionID", source)
        self.assertIn("output.metadata", source)
        self.assertIn("metadata?.sessionId !== taskResultID", source)
        self.assertIn("completed", source)

    def test_phase2_assurance_cites_runtime_evidence_and_keeps_denial_blocked(self) -> None:
        text = ASSURANCE_PATH.read_text(encoding="utf-8")
        harness = (ROOT / "docs" / "fifth-pick" / "harness.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("## Phase 2 Runtime Integration", text)
        self.assertIn(
            "tests/test_review_bridge.py::test_initial_pass_appends_one_run_bound_m2_receipt",
            text,
        )
        self.assertIn(
            "tests/test_review_plugin.py::test_plugin_registers_only_lifecycle_and_tool_observers",
            text,
        )
        for reference in (
            "tests/test_review_plugin.py::test_review_digest_binds_exact_material_before_bridge_transport",
            "tests/test_review_plugin.py::test_reviewer_result_is_correlated_by_exact_task_call_id",
            "tests/test_review_plugin.py::test_controller_dispatch_command_requires_confirmed_receipt",
            "tests/test_review_bridge.py::test_per_run_lock_serializes_independent_processes",
            "tests/test_review_bridge.py::test_concurrent_conflicting_verdicts_preserve_one_receipt_and_stop_one_writer",
        ):
            with self.subTest(reference=reference):
                self.assertIn(reference, text)
        self.assertIn("**BLOCKED — runtime verification not performed**", text)
        self.assertIn("No actual Reviewer write attempt", text)
        self.assertIn("m10-routing-4a668301ac3e", text)
        self.assertIn("m10-handoff-12da2b7620fa", text)
        self.assertIn("matching initial PASS receipt", harness)
        self.assertIn("Correlated native-denial evidence remains BLOCKED", agents)


if __name__ == "__main__":
    unittest.main()

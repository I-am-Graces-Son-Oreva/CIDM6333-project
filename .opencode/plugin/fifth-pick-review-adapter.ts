import { createHash, randomUUID } from "node:crypto"
import { spawn } from "node:child_process"
import type { Plugin } from "@opencode-ai/plugin"

const REVIEW_COMMAND = "fifth-pick-review"
const REVIEW_DISPATCH_COMMAND = "fifth-pick-review-dispatch"
const REVIEWER_AGENT = "fifth-pick-reviewer"
const RUN_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/
const SHA256_PATTERN = /^[0-9a-f]{64}$/
const MAX_RESPONSE_BYTES = 64 * 1024
const BRIDGE_TIMEOUT_MS = 15_000

type BridgeMetadata = {
  run_id: string
  subject: string
  initial_artifact_sha256: string
  current_artifact_sha256: string
  revision: 0 | 1
}

type ReviewMetadata = BridgeMetadata & {
  schema_version: 1
  review_material: string
}

type DispatchMetadata = Omit<BridgeMetadata, "revision"> & { schema_version: 1; revision: 1 }

type BridgeKind = "VERDICT" | "REVISION_DISPATCHED"

type BridgeResponse = {
  review_cycle_id: string
  state: "REVIEWED_FOR_JOSEPH" | "REVISION_REQUIRED" | "ESCALATE_TO_JOSEPH" | "STOPPED"
  correction_count: 0 | 1
  correction_available: boolean
  receipt_event_keys: string[]
}

type ReviewContext = {
  metadata: ReviewMetadata
  reviewCycleId: string
  invocationID: string
  reviewerCallID?: string
  verdictHandled: boolean
}

function record(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return
  return value as Record<string, unknown>
}

function parseUniqueObject(json: string): Record<string, unknown> | undefined {
  const data = record(JSON.parse(json) as unknown)
  if (!data) return
  // These schemas have no nested objects. Match whole JSON string tokens so values
  // containing quote/colon text cannot be mistaken for member names.
  const keys = new Set<string>()
  for (const [, token, colon] of json.matchAll(/("(?:[^"\\]|\\.)*")(\s*:)?/g)) {
    if (!colon) continue
    const key = JSON.parse(token) as string
    if (keys.has(key)) return
    keys.add(key)
  }
  return data
}

function decodeCommandEnvelope(raw: string): Record<string, unknown> | undefined {
  // OpenCode run wraps space-containing argv and escapes quotes, leaving backslashes intact.
  const envelope =
    raw.startsWith('"') && raw.endsWith('"') ? raw.slice(1, -1).replaceAll('\\"', '"') : raw
  return parseUniqueObject(envelope)
}

function parseMetadata(raw: string): ReviewMetadata | undefined {
  try {
    const data = decodeCommandEnvelope(raw)
    const expected = [
      "schema_version",
      "run_id",
      "subject",
      "initial_artifact_sha256",
      "current_artifact_sha256",
      "revision",
      "review_material",
    ]
    if (!data || Object.keys(data).sort().join("\0") !== expected.sort().join("\0")) return
    if (data.schema_version !== 1 || !Number.isInteger(data.revision)) return
    if (data.revision !== 0 && data.revision !== 1) return
    if (typeof data.run_id !== "string" || !RUN_ID_PATTERN.test(data.run_id)) return
    if (typeof data.subject !== "string" || !data.subject.trim()) return
    if (
      typeof data.initial_artifact_sha256 !== "string" ||
      !SHA256_PATTERN.test(data.initial_artifact_sha256)
    ) {
      return
    }
    if (
      typeof data.current_artifact_sha256 !== "string" ||
      !SHA256_PATTERN.test(data.current_artifact_sha256)
    ) {
      return
    }
    if (typeof data.review_material !== "string" || !data.review_material.trim()) return
    const materialDigest = createHash("sha256")
      .update(Buffer.from(data.review_material, "utf8"))
      .digest("hex")
    if (data.current_artifact_sha256 !== materialDigest) return
    if (data.revision === 0 && data.initial_artifact_sha256 !== materialDigest) return
    return data as ReviewMetadata
  } catch {
    return
  }
}

function parseDispatchMetadata(raw: string): DispatchMetadata | undefined {
  try {
    const data = decodeCommandEnvelope(raw)
    const expected = [
      "schema_version",
      "run_id",
      "subject",
      "initial_artifact_sha256",
      "current_artifact_sha256",
      "revision",
    ]
    if (!data || Object.keys(data).sort().join("\0") !== expected.sort().join("\0")) return
    if (data.schema_version !== 1 || data.revision !== 1) return
    if (typeof data.run_id !== "string" || !RUN_ID_PATTERN.test(data.run_id)) return
    if (typeof data.subject !== "string" || !data.subject.trim()) return
    if (
      typeof data.initial_artifact_sha256 !== "string" ||
      !SHA256_PATTERN.test(data.initial_artifact_sha256)
    ) {
      return
    }
    if (
      typeof data.current_artifact_sha256 !== "string" ||
      !SHA256_PATTERN.test(data.current_artifact_sha256)
    ) {
      return
    }
    return data as DispatchMetadata
  } catch {
    return
  }
}

function reviewCycleId(metadata: BridgeMetadata): string {
  const canonical = JSON.stringify({
    initial_artifact_sha256: metadata.initial_artifact_sha256,
    run_id: metadata.run_id,
    subject: metadata.subject,
  })
  return `review-${createHash("sha256").update(canonical).digest("hex")}`
}

function taskAgent(value: unknown): string | undefined {
  const args = record(value)
  if (!args) return
  for (const key of ["subagent_type", "agent", "agent_name"]) {
    if (typeof args[key] === "string") return args[key]
  }
}

function hasReviewMarker(value: unknown, context: ReviewContext): boolean {
  const args = record(value)
  if (!args) return false
  const marker = `FIFTH_PICK_REVIEW_TASK=${context.reviewCycleId}:${context.invocationID}`
  return typeof args.description === "string" && args.description.endsWith(` [${marker}]`)
}

function appendReviewMarker(
  parts: Array<{ type: string; description?: string }>,
  cycleId: string,
  invocationID: string,
): boolean {
  for (const part of parts) {
    if (part.type !== "subtask" || typeof part.description !== "string") continue
    // OpenCode passes the description as task metadata and uses the prompt for the child message.
    part.description = `${part.description} [FIFTH_PICK_REVIEW_TASK=${cycleId}:${invocationID}]`
    return true
  }
  return false
}

function replaceCommandText(parts: Array<{ type: string; text?: string }>, text: string): void {
  for (const part of parts) {
    if (part.type !== "text" || typeof part.text !== "string") continue
    part.text = text
  }
}

function stoppedControllerResult(reason: string): string {
  return JSON.stringify({
    state: "STOPPED",
    reason,
    receipt_event_keys: [],
    controller_instruction: "do not dispatch Builder; stop and escalate to Joseph",
  })
}

function controllerDispatchResult(response: BridgeResponse, expectedCycle: string): string {
  const expectedKey = expectedCycle + "-02-revision_attempt"
  const confirmed =
    response.review_cycle_id === expectedCycle &&
    response.state === "REVISION_REQUIRED" &&
    response.correction_count === 1 &&
    !response.correction_available &&
    response.receipt_event_keys.length === 1 &&
    response.receipt_event_keys[0] === expectedKey
  if (!confirmed) return stoppedControllerResult("REVISION_CONFIRMATION_REJECTED")
  return JSON.stringify({
    ...response,
    controller_instruction: "dispatch the single Builder correction now",
  })
}

function taskResultSessionID(output: string): string | undefined {
  return /^<task id="([A-Za-z0-9_-]+)" state="completed">\s*<task_result>[\s\S]*<\/task_result>\s*<\/task>$/.exec(
    output,
  )?.[1]
}

function parseBridgeResponse(raw: string, exitCode: number): BridgeResponse {
  const lines = raw.split(/\r?\n/)
  if (lines.at(-1) === "") lines.pop()
  if (lines.length !== 1 || !lines[0]) throw new Error("bridge stdout was not one JSON line")
  const data = parseUniqueObject(lines[0])
  const expected = [
    "review_cycle_id",
    "state",
    "correction_count",
    "correction_available",
    "receipt_event_keys",
  ]
  if (!data || Object.keys(data).sort().join("\0") !== expected.sort().join("\0")) {
    throw new Error("bridge response fields were invalid")
  }
  const states = [
    "REVIEWED_FOR_JOSEPH",
    "REVISION_REQUIRED",
    "ESCALATE_TO_JOSEPH",
    "STOPPED",
  ]
  if (
    typeof data.review_cycle_id !== "string" ||
    !/^review-[0-9a-f]{64}$/.test(data.review_cycle_id) ||
    typeof data.state !== "string" ||
    !states.includes(data.state) ||
    (data.correction_count !== 0 && data.correction_count !== 1) ||
    typeof data.correction_available !== "boolean" ||
    !Array.isArray(data.receipt_event_keys) ||
    data.receipt_event_keys.some((key) => typeof key !== "string")
  ) {
    throw new Error("bridge response values were invalid")
  }
  if ((exitCode === 0) !== (data.state !== "STOPPED")) {
    throw new Error("bridge response state did not match its exit status")
  }
  return data as BridgeResponse
}

function invokeBridge(
  directory: string,
  metadata: BridgeMetadata,
  kind: BridgeKind,
  verdictJson?: string,
): Promise<BridgeResponse> {
  const request: Record<string, unknown> = {
    schema_version: 1,
    kind,
    run_id: metadata.run_id,
    subject: metadata.subject,
    initial_artifact_sha256: metadata.initial_artifact_sha256,
    current_artifact_sha256: metadata.current_artifact_sha256,
    revision: kind === "REVISION_DISPATCHED" ? 1 : metadata.revision,
  }
  if (kind === "VERDICT") request.verdict_json = verdictJson

  return new Promise((resolve, reject) => {
    const child = spawn(
      "uv",
      ["run", "--no-sync", "python", "-m", "fifth_pick.review_bridge"],
      { cwd: directory, shell: false, stdio: ["pipe", "pipe", "pipe"] },
    )
    const stdout: Buffer[] = []
    let outputBytes = 0
    let transportFailed = false
    const fail = (error: Error) => {
      if (transportFailed) return
      transportFailed = true
      clearTimeout(timer)
      reject(error)
      child.kill("SIGTERM")
    }
    const timer = setTimeout(() => fail(new Error("bridge process timed out")), BRIDGE_TIMEOUT_MS)
    child.on("error", fail)
    child.stdin.on("error", fail)
    child.stdout.on("error", fail)
    child.stderr.on("error", fail)
    child.stdout.on("data", (chunk: Buffer) => {
      if (transportFailed) return
      outputBytes += chunk.length
      if (outputBytes > MAX_RESPONSE_BYTES) {
        fail(new Error("bridge response exceeded its size limit"))
        return
      }
      stdout.push(chunk)
    })
    child.stderr.resume()
    child.once("close", (code) => {
      clearTimeout(timer)
      if (transportFailed) return
      try {
        if (code === null) throw new Error("bridge terminated without an exit status")
        resolve(parseBridgeResponse(Buffer.concat(stdout).toString("utf8"), code))
      } catch (error) {
        reject(error)
      }
    })
    try {
      child.stdin.end(JSON.stringify(request))
    } catch (error) {
      fail(error instanceof Error ? error : new Error("bridge stdin write failed"))
    }
  })
}

function appendControllerResult(
  output: string,
  response: BridgeResponse,
  metadata: ReviewMetadata,
): string {
  const dispatchRequest =
    response.state === "REVISION_REQUIRED" && response.correction_available
      ? `\nBefore dispatching the Builder, call /fifth-pick-review-dispatch with ` +
        `${JSON.stringify({
          schema_version: 1,
          run_id: metadata.run_id,
          subject: metadata.subject,
          initial_artifact_sha256: metadata.initial_artifact_sha256,
          current_artifact_sha256: metadata.current_artifact_sha256,
          revision: 1,
        })}. Dispatch only after it confirms the REVISION_ATTEMPT receipt.`
      : ""
  return `${output}\n\nFifth Pick review controller response: ${JSON.stringify(response)}${dispatchRequest}`
}

export const FifthPickReviewAdapter: Plugin = async ({ directory }) => {
  console.info("[fifth-pick-review-adapter] activated")
  const contexts = new Map<string, ReviewContext>()

  return {
    "command.execute.before": async (input, output) => {
      if (input.command === REVIEW_DISPATCH_COMMAND) {
        if (!output.parts.some((part) => part.type === "text" && typeof part.text === "string")) {
          console.warn("[fifth-pick-review-adapter] STOPPED: no controller response channel for dispatch")
          return
        }
        const metadata = parseDispatchMetadata(input.arguments)
        if (!metadata) {
          replaceCommandText(output.parts, stoppedControllerResult("INVALID_DISPATCH_ENVELOPE"))
          return
        }
        try {
          const response = await invokeBridge(directory, metadata, "REVISION_DISPATCHED")
          replaceCommandText(output.parts, controllerDispatchResult(response, reviewCycleId(metadata)))
        } catch {
          replaceCommandText(
            output.parts,
            stoppedControllerResult("REVISION_RECEIPT_UNAVAILABLE"),
          )
        }
        return
      }
      if (input.command !== REVIEW_COMMAND) return
      const metadata = parseMetadata(input.arguments)
      if (!metadata) {
        contexts.delete(input.sessionID)
        return
      }
      const cycleId = reviewCycleId(metadata)
      const invocationID = randomUUID()
      if (!appendReviewMarker(output.parts, cycleId, invocationID)) {
        contexts.delete(input.sessionID)
        return
      }
      contexts.set(input.sessionID, {
        metadata,
        reviewCycleId: cycleId,
        invocationID,
        verdictHandled: false,
      })
    },
    "tool.execute.before": async (input, output) => {
      const context = contexts.get(input.sessionID)
      if (
        input.tool !== "task" ||
        !context ||
        context.reviewerCallID !== undefined ||
        taskAgent(output.args) !== REVIEWER_AGENT ||
        !hasReviewMarker(output.args, context)
      ) {
        return
      }
      context.reviewerCallID = input.callID
    },
    "tool.execute.after": async (input, output) => {
      const context = contexts.get(input.sessionID)
      if (
        input.tool !== "task" ||
        !context ||
        context.reviewerCallID !== input.callID ||
        context.verdictHandled ||
        taskAgent(input.args) !== "fifth-pick-reviewer"
      ) {
        return
      }
      const taskResultID = taskResultSessionID(output.output)
      const metadata = record(output.metadata)
      if (!taskResultID || metadata?.sessionId !== taskResultID) {
        output.output = `${output.output}\n\nFifth Pick review controller is STOPPED; task result envelope correlation failed.`
        contexts.delete(input.sessionID)
        return
      }
      context.verdictHandled = true
      try {
        const response = await invokeBridge(
          directory,
          context.metadata,
          "VERDICT",
          output.output,
        )
        output.output = appendControllerResult(output.output, response, context.metadata)
        contexts.delete(input.sessionID)
      } catch {
        output.output = `${output.output}\n\nFifth Pick review controller response: ${stoppedControllerResult("VERDICT_TRANSPORT_UNAVAILABLE")}`
        contexts.delete(input.sessionID)
      }
    },
  }
}

import type { Plugin } from "@opencode-ai/plugin"

export const Tp4ReadonlyGate: Plugin = async () => {
  return {
    "permission.ask": async (input, output) => {
      if (process.env.E8_TP4_GATE !== "1") {
        return
      }

      const permission = String(input.type ?? "").toLowerCase()

      if (
        permission.includes("edit") ||
        permission.includes("write") ||
        permission.includes("apply_patch")
      ) {
        output.status = "deny"
      }
    },
  }
}

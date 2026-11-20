import { spawnSync } from "node:child_process";

export const GuardPlugin = async () => ({
  "tool.execute.before": async (input, output) => {
    const result = spawnSync("uv", ["run", "python", "guard/guard.py"], {
      input: JSON.stringify({ tool: input.tool, args: output.args }),
      encoding: "utf8",
    });
    if (result.status !== 0) {
      const reason = result.stdout.trim() || result.stderr.trim() || result.error?.message;
      throw new Error(reason || "blocked by guard");
    }
  },
});

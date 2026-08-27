import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PiOrchestrationTests(unittest.TestCase):
    def test_browser_uses_raw_playwright_and_catches_awaited_errors(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")

        self.assertNotIn("downloadHelper", extension)
        self.assertNotIn("guardedEvents", extension)
        self.assertIn("await run(page, context, browserDownloads, projectRoot)", extension)
        self.assertIn("catch (error)", extension)
        self.assertIn('pi.on("session_shutdown"', extension)
        self.assertIn("await context.close().catch", extension)

    def test_solver_uses_orca_terminal_and_reviewer_uses_ephemeral_pi(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")

        self.assertIn('name: "reverser_solve"', extension)
        self.assertIn('name: "reverser_review"', extension)
        self.assertIn('"--mode", "json", "-p", "--no-session", "--approve"', extension)
        self.assertIn('"--tools", AGENT_TOOLS[role].join(",")', extension)
        self.assertIn('runPiAgent("reviewer"', extension)
        solve_block = extension.split('name: "reverser_solve"', 1)[1].split(
            'name: "reverser_review"', 1
        )[0]
        self.assertIn('splitArgs.push("--direction", solverTerminal ? "horizontal" : "vertical"', solve_block)
        self.assertIn('if (split.code !== 0 && solverTerminal)', solve_block)
        self.assertIn('solverTerminal = undefined', solve_block)
        self.assertIn('"terminal", "send", "--terminal", handle', solve_block)
        self.assertIn("await pi.exec", solve_block)
        self.assertIn('AGENT_TOOLS.solver.join(",")', solve_block)
        self.assertNotIn('await runPiAgent("solver"', solve_block)
        self.assertIn('event.type === "tool_execution_start"', extension)
        self.assertIn('event.type === "tool_execution_end"', extension)
        self.assertIn("elapsedText", extension)
        self.assertIn("setInterval", extension)
        self.assertIn("const failed = event.isError ||", extension)

    def test_child_agents_are_scoped_and_do_not_receive_browser(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")
        solver_block = extension.split("solver: [", 1)[1].split("],", 1)[0]
        reviewer_block = extension.split("reviewer: [", 1)[1].split("],", 1)[0]

        self.assertIn('"reverser_exec"', solver_block)
        self.assertNotIn('"reverser_browser"', solver_block)
        self.assertNotIn('"reverser_solve"', solver_block)
        self.assertNotIn('"reverser_browser"', reviewer_block)
        self.assertTrue((ROOT / ".pi" / "agents" / "solver.md").is_file())
        self.assertTrue((ROOT / ".pi" / "agents" / "reviewer.md").is_file())

    def test_parent_cannot_bypass_solver_layout_with_raw_orca_split(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")
        self.assertIn(r"orca(?:\.exe)?\s+terminal\s+(?:split|create)", extension)

    def test_flag_tool_requires_evidence_and_solution_search_is_local_only(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")
        self.assertIn("evidence_run: Type.Integer", extension)
        self.assertIn('"--evidence-run"', extension)
        self.assertNotIn("public web results", extension)

    def test_agent_progress_updates_include_challenge_id(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")
        self.assertIn(
            'const challengeLabel = title ? `${title} (${challengeId})` : challengeId;',
            extension,
        )
        self.assertIn('text: `[${roleLabel} · ${challengeLabel}] ${status}`', extension)
        self.assertIn("state?.title", extension)
        self.assertIn('publish("에이전트 시작")', extension)
        self.assertIn('publish(`에이전트 ${code === 0 ? "완료" : "종료"}', extension)


if __name__ == "__main__":
    unittest.main()

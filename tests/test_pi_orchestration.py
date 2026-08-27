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

    def test_solver_and_reviewer_use_orca_without_blocking_parent(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")

        self.assertIn('name: "reverser_solve"', extension)
        self.assertIn('name: "reverser_review"', extension)
        self.assertIn('"--tools", AGENT_TOOLS[role].join(",")', extension)
        self.assertIn('agentCommand("reviewer"', extension)
        self.assertIn('"terminal", "wait"', extension)
        self.assertIn('runCli(["reviewer-start"', extension)
        self.assertIn('watchJob("reviewer"', extension)
        solve_block = extension.split('name: "reverser_solve"', 1)[1].split(
            'name: "reverser_review"', 1
        )[0]
        self.assertIn('args.push("--direction", base ? "horizontal" : "vertical"', extension)
        self.assertIn('if (split.code !== 0 && base)', extension)
        self.assertIn('"terminal", "send", "--terminal", handle', solve_block)
        self.assertIn("await pi.exec", solve_block)
        self.assertIn('agentCommand("solver"', solve_block)
        self.assertIn('runCli(["solver-start"', solve_block)
        self.assertIn('pi.sendMessage(', extension)
        self.assertIn('deliverAs: "followUp"', extension)
        self.assertIn('file?.toString() === `${role}.json`', extension)
        self.assertIn('runCli(["solver-finish", p.challenge_id]', extension)
        self.assertIn('name: "reverser_recon"', extension)
        self.assertIn('name: "reverser_hypothesis"', extension)
        self.assertIn('"gpt-5.6-luna"', extension)
        self.assertIn('await pi.setModel(model)', extension)
        self.assertIn('"--hypothesis", p.hypothesis_id', extension)
        self.assertIn('["--target", p.target]', extension)
        self.assertIn('["--parent-id", p.parent_id]', extension)
        self.assertIn('runCli(["reviewer-finish"', extension)

    def test_child_agents_are_scoped_and_do_not_receive_browser(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")
        solver_block = extension.split("solver: [", 1)[1].split("],", 1)[0]
        reviewer_block = extension.split("reviewer: [", 1)[1].split("],", 1)[0]

        self.assertIn('"reverser_exec"', solver_block)
        self.assertIn('"reverser_recon"', solver_block)
        self.assertNotIn('"reverser_browser"', solver_block)
        self.assertNotIn('"reverser_solve"', solver_block)
        self.assertNotIn('"reverser_browser"', reviewer_block)
        self.assertNotIn('"reverser_exec"', reviewer_block)
        self.assertNotIn('"reverser_writeup"', solver_block)
        self.assertTrue((ROOT / ".pi" / "agents" / "solver.md").is_file())
        self.assertTrue((ROOT / ".pi" / "agents" / "reviewer.md").is_file())
        solver_prompt = (ROOT / ".pi" / "agents" / "solver.md").read_text(encoding="utf-8")
        self.assertIn("workspace 내부에만", solver_prompt)
        self.assertIn("falsifier", solver_prompt)
        self.assertIn("entry point", solver_prompt)
        self.assertIn("parent_id", solver_prompt)

    def test_parent_cannot_bypass_solver_layout_with_raw_orca_split(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")
        self.assertIn(r"orca(?:\.exe)?\s+terminal\s+(?:split|create)", extension)

    def test_flag_tool_requires_evidence_and_solution_search_is_local_only(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")
        self.assertIn("evidence_run: Type.Integer", extension)
        self.assertIn('"--evidence-run"', extension)
        self.assertNotIn("public web results", extension)

    def test_completion_messages_include_challenge_id(self):
        extension = (ROOT / ".pi" / "extensions" / "Reverser.ts").read_text(encoding="utf-8")
        self.assertIn('content: `[${label}] ${challengeId} 완료 · ${job.result}`', extension)


if __name__ == "__main__":
    unittest.main()

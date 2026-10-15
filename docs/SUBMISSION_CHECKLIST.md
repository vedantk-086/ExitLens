# Hackathon Submission Checklist

Use this before submitting. The authoritative event handbook takes precedence if organizers publish an update.

- [ ] Create a **public GitHub fork** of the official target repository. Keep the fork relationship visible; a ZIP or a newly created unrelated repository is not a substitute for a fork.
- [ ] Use the event repository naming convention `H26_TeamName_ExitLens` and replace `TeamName` with the actual team name (not a member name unless that is the agreed team name).
- [ ] Preserve the upstream LinkWatch source files and original MIT license notice. Add license/attribution notices for new third-party assets as appropriate.
- [ ] Include the root project README, backend README, frontend README, architecture diagram, setup instructions, environment examples, and the API/capsule contract.
- [ ] Demonstrate dynamic analysis of the real LinkWatch repository, not prewritten sample findings.
- [ ] Demonstrate meaningful Gemma 4 use and record the actual local model tag/provider method. Default to local Ollama; hosted inference remains off unless organizers explicitly approve it under event rules.
- [ ] Do not make paid API calls or rely on cloud services prohibited by the handbook.
- [ ] Capture authentic run evidence: command, runtime version, test profile, timestamps, statuses, exit codes where a command actually ran, model provenance and known limitations.
- [ ] Verify every flagged dependency has all nine Dependency Exit Capsule sections. Test JSON/Markdown exports for parity.
- [ ] State which replacement checks were skipped and why; never pass off suggestions or test fixtures as real verification/Gemma output.
- [ ] Run checks from a clean checkout and include exact commands/results in the final demo notes.
- [ ] Provide the requested six-slide presentation if required by the event handbook; ensure its claims match the actual working implementation.
- [ ] Review `git status` and remove `.env`, credentials, model weights, caches, virtual environments, `node_modules`, private repositories and generated reports before pushing.
- [ ] Verify the submitted GitHub URL, default branch, README rendering, license and downloadable/presentation links.

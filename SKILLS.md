---
mode: 'agent'
description: 'Add visual snapshots to Playwright integration tests using the repo snapshot plugin setup and broad masking.'
---
## Add Visual Snapshots

Add visual snapshots to Playwright integration tests in this repo.

Requirements:

- Use the existing `pytest-playwright-visual-snapshot` package already present in the project.
- Prefer setting snapshot defaults globally in `pytest_configure` rather than creating local helper wrappers unless there is a hard blocker.
- Prefer broad, maintainable masks over per-field masks.
  - Mask whole form-control regions like `form input`, `form textarea`, `form button`, checkbox/combobox controls, and third-party payment/media widgets.
  - Do not overfit masks to individual fields unless absolutely necessary.
- Add concise comments for every masked selector explaining what it is and why it is masked.
- Add `data-testid` hooks in the frontend only when they make masking or snapshot targeting materially simpler.
- Avoid pinning factories or hardcoding static test data just to make snapshots stable unless there is no simpler alternative.
- Choose visually important integration flows and add multiple snapshots per test when useful to capture meaningful states of the workflow.
- Keep snapshots focused on stable user-visible layout, not dynamic IDs, third-party embeds, or user-entered values.

Validation requirements:

- Run the affected tests once with `--update-snapshots` to generate baselines.
- Then run the same tests at least twice more without updating snapshots.
- If snapshots are flaky, tighten the global or broad masks first before adding per-field masks or hardcoded test data.
- If a test becomes timing-sensitive, prefer increasing the existing integration timeout usage over making the snapshot strategy more complex.

Deliverable:

- Make the code changes directly.
- Tell me which tests got snapshots, what was masked globally vs locally, and which test commands you ran.
- Call out any flow that could not be executed because of existing feature flags or environment constraints.

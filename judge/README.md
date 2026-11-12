# Official judge

The workflow [`.github/workflows/judge.yml`](../.github/workflows/judge.yml)
scores the submissions on the website. It runs:

- when a participant saves a lens file (the website starts the workflow),
- every 30 minutes, to catch anything missed,
- by hand, from the Actions tab.

How it works:

- The scoring code comes from a release tag (for example `v2.1.0`), never from
  `main`. Each challenge on the website records the evaluator version that
  judges it, and the workflow matrix lists the tags in use.
- Each submission runs in its own process with a 30-minute timeout, on a Linux
  runner in the pinned environment, so the result is official.
- The judge writes a result only if the submission did not change during the
  evaluation. A newer submission is judged on the next run.
- The public log shows only submission ids, statuses and scores. Lens files and
  reports stay private until the challenge deadline.

The workflow needs two repository secrets: `SUPABASE_URL` and
`SUPABASE_SERVICE_ROLE_KEY`.

## Add a challenge

1. Add its specification to `CHALLENGES` in `challenge_evaluator.py`, its rules
   to `RULES.md` and a reference design to `examples/`.
2. Release a new tag.
3. Add the tag to the workflow matrix and map the website slug to the challenge
   name in [`challenges.json`](challenges.json).

# Rules for AI agents working on Calimara

Several agents work on this repo at the same time, and **no human reviews the code**.
These rules replace human review. Follow them exactly. If a rule blocks you, stop and
tell the user instead of working around it.

## 0. This machine IS production

- `/home/dan/calimara2` (the main checkout) is the **live site** (calimara.ro).
  `calimara.service` runs `run.py --serve` from that folder, on port 8000.
- `.env` there points at the **production database** `calimara_db`.

Therefore:

- **Never edit, commit, check out, stash or reset in `/home/dan/calimara2`** unless you
  are the integrator doing the deploy steps in section 3.
- **Never run `python run.py`** (without `--serve` it restarts the live service).
  Never set `CALIMARA_RESET_DATABASE=true` (it rebuilds the database from `schema.sql`).
- Agents **may connect to and change the production database** when a task needs it
  (the site has no real users yet). Before any write, take a backup:
  `sudo -u postgres pg_dump -Fc calimara_db > /home/dan/backups/calimara_db-$(date +%Y%m%d-%H%M%S).dump`.
  Run writes as the table owner (`SET ROLE calimara_user`) and mention what you changed in
  your report. Scripts such as `scripts/seed.py`, `scripts/e2e_data.py` and the browser
  E2E in `scripts/test_all.py` write to this database, so only run them on purpose.
- Never copy `.env` or `keys/` into a worktree, never print secrets, never commit them.
- Never force-push, never rewrite `main` history, never delete branches you did not create
  (the integrator may delete branches it merged).

## 1. Starting work (every feature agent)

One agent = one task = one branch = one worktree.

```bash
cd /home/dan/calimara2
git worktree add .claude/worktrees/<short-name> -b feat/<short-name> main   # or fix/<short-name>
cd .claude/worktrees/<short-name>
```

(Claude Code's own `EnterWorktree` / `--worktree` is fine too. Afterwards run
`git rebase main` so you start from what production actually runs.)

- Work **only** inside your worktree. Never touch another agent's worktree or branch.
- Keep the task small and focused. No drive-by refactors, reformatting or renames
  outside your task. They cause merge conflicts with the other agents.
- One-time setup in a new worktree (it has no `node_modules`, no `dist`, no `.venv`):
  ```bash
  (cd frontend && npm ci && npm run build)
  ```
  Use the shared interpreter: `PY=/home/dan/calimara2/.venv/bin/python`.
- Do not start the app server to "check it". Verify with tests.

## 2. Finishing work (every feature agent)

1. Add or update tests for what you changed. Tests are the only reviewer here.
2. Rebase onto the latest `main` and re-test:
   ```bash
   git fetch origin && git rebase main
   (cd frontend && npm run build)
   $PY -m pytest tests -q -p no:cacheprovider
   ```
3. **Tests rule:** no *new* failures compared to `main`. If a test fails on your branch,
   check whether it also fails on `main`. If it fails only on your branch, fix it.
   (At the time of writing, `main` has 2 known failures: stale string-matching tests
   `test_landing_shuffle_softens_footer_metric_transition` and
   `test_navbar_splits_calimara_and_notifications_controls`.)
4. Review your own diff (`git diff main...HEAD`) for bugs, leftover debug code,
   secrets, and unrelated changes. Claude Code agents: run `/code-review` on it.
5. Commit with a clear message saying *what* changed and *why*.
6. **Push your branch. Pushing means "ready to deploy":** `git push -u origin feat/<short-name>`.
   Only push finished, tested work. To back up unfinished work, push it as `wip/<name>`.
   The integrator ignores `wip/*` branches.
7. Never merge into `main` and never deploy yourself, unless the user asked you to be
   the integrator.

### Database changes

`run.py` runs **no migrations**. Changing `schema.sql` alone does nothing to production.
If your task changes the schema:

- Update `schema.sql` (used for fresh installs), **and**
- add `migrations/<YYYYMMDD>_<description>.sql` that brings the live DB to the new state.
  It must be **idempotent** (`IF NOT EXISTS`, etc.) and **additive only**: no `DROP`,
  no column renames, no type narrowing, no data deletion. Destructive changes need the
  user's explicit approval.
- Only one in-flight branch should touch the schema at a time. If `migrations/` already has
  unmerged changes on another pushed branch, tell the user instead of adding yours.

## 3. Deploying (only when the user asks an agent to "deploy" / "ship" / "push to production")

That agent is the **integrator**. Only one integrator may run at a time.

```bash
mkdir /home/dan/calimara2/.git/deploy.lock || { echo "another deploy is running"; exit 1; }
# ...always `rmdir /home/dan/calimara2/.git/deploy.lock` when finished, success or failure
```

**a. Preflight**
- In `/home/dan/calimara2`, `git status --porcelain` must show no tracked changes. If it
  does, stop and report. Never discard them.
- The production checkout must be on `main`. If it is on another branch **at the same
  commit** as `main`, `git checkout main` (no files change). Otherwise stop and report.
- Record `OLD=$(git -C /home/dan/calimara2 rev-parse main)` for rollback.

**b. Build the release in a worktree, one branch at a time**
```bash
cd /home/dan/calimara2
git fetch origin --prune
git branch -r --no-merged main | grep -E 'origin/(feat|fix)/'    # the ready queue
git worktree add .claude/worktrees/integration -b integration main
```
For each ready branch, oldest first:
1. Read `git log main..origin/<branch>` and `git diff main...origin/<branch>`. Review it
   for correctness, security (injection, auth checks, secrets), destructive SQL,
   and accidental changes outside the task. Claude Code: run `/code-review` on it.
   Skip the branch if you find a real problem.
2. `git merge --no-ff origin/<branch>`. If there are conflicts, resolve them only if the
   resolution is mechanical and obvious. Otherwise `git merge --abort` and skip the branch.
3. `(cd frontend && npm ci && npm run build)` and
   `$PY -m pytest tests -q -p no:cacheprovider`. If there is any new failure,
   `git reset --hard HEAD~1` (this resets only the integration branch) and skip the branch.

Merge one branch at a time, testing after each, so a broken branch is caught on its own.

**c. Back up, migrate, deploy**
```bash
mkdir -p /home/dan/backups
sudo -u postgres pg_dump -Fc calimara_db > /home/dan/backups/calimara_db-$(date +%Y%m%d-%H%M%S).dump
git diff --name-only main integration -- migrations/    # new migrations, if any
# apply each new migration, in filename order, as the table owner, in one transaction:
# (read via stdin: the postgres user cannot read files under /home/dan)
sudo -u postgres psql -d calimara_db -v ON_ERROR_STOP=1 -1 -c 'SET ROLE calimara_user' -f - < migrations/<file>.sql
cd /home/dan/calimara2 && git merge --ff-only integration      # production checkout is on main
sudo systemctl restart calimara
```
If a migration fails, stop. It ran in a transaction, so nothing was applied. Do not deploy.

**d. Verify.** Startup rebuilds the frontend, so allow up to ~3 minutes.
- `systemctl is-active calimara` must print `active`.
- `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/` must print `200`.
- `journalctl -u calimara --since "-5 min" | grep -iE "traceback|error"` must show nothing new.

**e. If verification fails, roll back immediately:**
```bash
cd /home/dan/calimara2 && git reset --hard $OLD && sudo systemctl restart calimara
```
Then verify again. Migrations are additive, so the old code still runs. Only restore the
DB dump if the user approves it. Report which branch most likely caused the failure.

**f. On success**
- `git push origin main` (this keeps GitHub and new worktrees up to date).
- Delete the merged branches on the remote (`git push origin --delete feat/<x>`) and
  remove the `integration` worktree and branch. Leave other agents' worktrees alone and
  list them in the report.
- Keep only the newest 5 dumps in `/home/dan/backups`.
- Release the lock.

**g. Report to the user:** what was deployed (branches and commits), what was skipped and
why, test results, migrations applied, backup file name, and health-check results.

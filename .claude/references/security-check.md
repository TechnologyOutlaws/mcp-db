# Security Check — Run Before Every Commit

## Step 1 — Secrets scan
grep -r -i "accountkey\|connectionstring\|client_secret\|api_key\|password\|token" \
  --include="*.py" --include="*.json" --include="*.yaml" --include="*.env" \
  . 2>&1 | grep -v ".gitignore" | grep -v "security-check.md"

Expected: no output. Any match = STOP. Remove secret. Use env var or Key Vault ref.

## Step 2 — .env not staged
git status | grep -i ".env"
Expected: no output. If .env appears as staged: git rm --cached .env. Fix .gitignore.

## Step 3 — No hardcoded endpoints
grep -r "documents.azure.com\|vault.azure.net\|applicationinsights.azure.com" \
  --include="*.py" . 2>&1

Expected: no output. Endpoints must come from env vars only.

## Step 4 — License check for new dependencies
For any new package added to requirements.txt this session:
  pip show <package> | grep -i license
Confirm: MIT, Apache, or BSD. Block: AGPL, GPL, LGPL (unless JT approves).

## Step 5 — No TO internal references
grep -r -i "marcella\|technology.outlaws\|mcf.protocol\|technologyoutlaws" \
  --include="*.py" --include="*.md" . 2>&1

Expected: no output. This is a public repo.

ALL FIVE CHECKS MUST BE CLEAN BEFORE COMMITTING.

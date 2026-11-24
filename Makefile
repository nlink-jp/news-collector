.PHONY: test lint vuln

test:
	uv run pytest

lint:
	uv run pyright

# vuln: known advisories in the locked dependencies; exits 1 on a finding.
# Run before tagging a release (CONVENTIONS §Release Checklist).
vuln:
	uv audit --frozen --preview-features audit-command

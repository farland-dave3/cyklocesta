"""eBike route-map GPX pipeline.

Stdlib-only. See CLAUDE.md for the non-negotiable privacy rules this
package implements: privacy-zone trim with salted radius jitter,
emit-by-whitelist GPX writing, and the routes.json contract.

Entry point: `python3 -m pipeline <report|process|rebuild-index>`.
"""

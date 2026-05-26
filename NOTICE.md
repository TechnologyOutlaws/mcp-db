# NOTICE

MCP-DB
Copyright (c) 2026 Technology Outlaws LLC. All rights reserved.

This repository is licensed under the MIT License. See [LICENSE](./LICENSE)
for the terms governing use of the source code.

---

## Patent Notice

The Compound Query Tier architecture implemented in this repository is
covered under a United States patent application pending before the
United States Patent and Trademark Office (USPTO), filed by Technology
Outlaws LLC.

The pending application covers, without limitation, the following novel
combinations:

1. A Compound Query Tier embedded inside Model Context Protocol (MCP)
   server middleware that classifies inbound tool calls as narrow or
   compound and routes compound calls through a database-backed
   assembly layer.
2. An intent-to-query-strategy routing table consumed at MCP
   tool-invocation time, mapping `(domain, intent)` tuples to
   pre-materialized query strategies without per-tool code changes.
3. A materialized view, refreshed via write-side triggers, that is
   consumed directly by MCP tool implementations to satisfy compound
   queries in a single point-read.
4. A single compound attestation record bearing an `assembled_sources`
   provenance manifest and a SHA-256 result hash, replacing the N
   correlated attestation records that a narrow-tool chain would
   otherwise produce.
5. A staleness-triggered fallback that detects out-of-date materialized
   views and transparently degrades to the equivalent narrow-tool chain
   for the duration of the staleness window.

The MIT License granted over the source code in this repository does
not grant, by implication, estoppel, or otherwise, any license to any
patent claims of Technology Outlaws LLC. All patent rights are
expressly reserved.

For patent licensing inquiries:

Technology Outlaws LLC
Jason Tesso
jt@technologyoutlaws.com

---

## Defensive Publication

A defensive publication establishing prior art for this pattern,
dated 2026-04-26, is provided in [PRIOR_ART.md](./PRIOR_ART.md).

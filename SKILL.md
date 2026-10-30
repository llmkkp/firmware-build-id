---
name: firmware-build-id
description: Add plaintext firmware build IDs (FWID) and source-snapshot archiving to an embedded project so a flashed MCU's ID can later retrieve the exact source. Use when the user asks for firmware traceability, build provenance, source archiving, or recovering source from a device.
---

# Firmware Build ID (FWID)

Implement the FWID convention in the current embedded project. `SPEC.md` in this directory is the normative source of truth; read it and `schema/build-record.schema.json` before changing the project. This file is the operational summary.

## Target

Aim for **FWID Core** conformance. Use the **Production** profile when the project ships to production. Follow SPEC.md §4–§10.

## Procedure

1. Inspect the project: build system, build command, flash command, MCU/framework, and any UART/debug output available at boot.
2. Add a pre-build step that:
   - snapshots every build input, including untracked files, submodules, dependency lockfiles, build configs, and the toolchain version (SPEC §5.1);
   - assigns a plaintext ID: 12–16 data characters from Crockford Base32 plus two CRC-8 check characters (SPEC §4, Appendix A);
   - writes a generated header/source containing `FWID:<body>` in a non-optimizable section;
   - records the snapshot hash.
3. Build from that exact snapshot. Do not build from a tree that changed after the snapshot.
4. After the build, verify the canonical ID string exists in the final binary/hex. Fail the build if it does not.
5. Archive the snapshot and a Build Record (SPEC §6, JSON Schema) before the image is flashed or distributed. Only allow flashing after the archive write is verified by reading it back.
6. Add boot-time output and a query command. Keep the ID plaintext.
7. Provide a retrieval path: ID -> fetch record and snapshot -> verify hashes -> restore a buildable project.

## Rules

- Plaintext ID. Do not add cryptography unless the user explicitly asks.
- Use the exact ID format and check characters from SPEC §4. Do not invent another ID scheme.
- Snapshot first, build from the snapshot, archive the same inputs.
- Flash the exact artifact that was hashed and archived. Never rebuild between archive and flash.
- The archived bundle must be sufficient to rebuild: dependencies, config, toolchain, generated files, build steps.
- Scan for secrets before upload; default to private storage.
- Keep the ID independent of signing keys and platform URLs.
- State assumptions instead of asking when the target is ambiguous.

## Deliverables

- Generated files clearly marked, e.g. `fwid_build.h`, `fwid_build.c`.
- A `fwid fetch <id>`-style retrieval path.
- `record.json` for each build, validated against the schema.
- Documentation of the archive backend, retention, and access model.
- A short note in the project README explaining how to recover source from an ID.

## Non-goals

- Recovering source from a binary.
- Anti-counterfeiting or secure boot; mention as optional follow-ups.
- Forcing a specific hosting platform.

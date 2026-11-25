# ADR E12 · Wheel release and rollback

Ship The Fifth Pick as a versioned wheel in an isolated local environment.
The user invokes the installed CLI. No service or provider account is
required for the release smoke check.

A Docker image could pin the operating-system layer but would introduce a
daemon and a second runtime path. Running directly from Git is useful for
development but cannot prove that a prior deployment restored identical
artifact bytes. The wheel path preserves released bytes under their SHA-256
and installs a candidate into a fresh environment before switching the
current pointer. Rollback checks the recorded hash before installation.
This uses local disk and preserves each installed environment until an
operator chooses to archive it. The experiment uses synthetic inputs and
an isolated deploy root.

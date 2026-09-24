#!/usr/bin/env bash
#
# Install the flight-fare-research skill into a Hermes skills directory.
#
# Target resolution (first match wins):
#   1. $HERMES_SKILLS_DIR        explicit override
#   2. Hermes profile skills dir, from $HERMES_HOME (e.g. ~/.hermes/profiles/me)
#   3. $HERMES_HOME/skills when set and HERMES_HOME != HOME (rooted installs)
#   4. ~/.hermes/skills/         Hermes default
#
# The canonical tree lives at <repo>/skill (SKILL.md + references/). This
# script removes any prior flat $target/flight-fare-research/ copy first and
# copies fresh, so stale files never linger (idempotent install).
# Existing category-based copies are not deleted automatically; choose an
# explicit HERMES_SKILLS_DIR to update their parent directory.
#
# Run from the repo root:  integrations/hermes/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="${SCRIPT_DIR}/../../skill"

if [[ ! -d "${SKILL_SRC}" || ! -f "${SKILL_SRC}/SKILL.md" ]]; then
    echo "error: canonical skill not found at ${SKILL_SRC}" >&2
    echo "expected to run from the repo root via integrations/hermes/install.sh" >&2
    exit 1
fi

if [[ -n "${HERMES_SKILLS_DIR:-}" ]]; then
    TARGET="${HERMES_SKILLS_DIR}"
elif [[ -n "${HERMES_HOME:-}" ]]; then
    if [[ -d "${HERMES_HOME}/skills" ]]; then
        TARGET="${HERMES_HOME}/skills"
    elif [[ "${HERMES_HOME}" != "${HOME}" ]]; then
        TARGET="${HERMES_HOME}/skills"
    else
        TARGET="${HOME}/.hermes/skills"
    fi
else
    TARGET="${HOME}/.hermes/skills"
fi

DEST="${TARGET}/flight-fare-research"

# Idempotency: drop any previous flat copy so stale files do not linger.
rm -rf "${DEST}"
mkdir -p "${TARGET}"
cp -R "${SKILL_SRC}" "${DEST}"

echo "Installed flight-fare-research skill to: ${DEST}"
echo "  SKILL.md:  ${DEST}/SKILL.md"
echo "  references: ${DEST}/references/"
echo "Note: the browser-act skill must be installed separately."

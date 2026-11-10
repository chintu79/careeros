"""
CareerOS Matching Engine Release Registry.
Authoritative source of matching engine releases and monotonic integer generations.

Rules:
1. Every release has a unique semantic version and a strictly monotonic integer generation.
2. Generations never decrease: release N+1 must have generation > release N.
3. Workers in the same deployment must run identical engine configurations.
4. If an algorithm must be rolled back, it must be deployed as a new release with an increased generation.
"""

from typing import Dict, Optional, Tuple


# Authoritative Release Registry: version string -> monotonic integer generation
MATCHING_ENGINE_RELEASES: Dict[str, int] = {
    "1.0.0": 1,
    "1.9.0": 1,
    "1.10.0": 2,
    "2.0.0": 2,
    "2.1.0": 3,
    "2.2.0": 4,
}

# The default active engine version and generation
DEFAULT_ACTIVE_ENGINE_VERSION = "2.0.0"
DEFAULT_ACTIVE_ENGINE_GENERATION = MATCHING_ENGINE_RELEASES[DEFAULT_ACTIVE_ENGINE_VERSION]


def get_canonical_engine_generation(version: str) -> int:
    """
    Returns the canonical integer generation for a given semantic version.
    Defaults to 1 for unmapped legacy versions.
    """
    return MATCHING_ENGINE_RELEASES.get(version, 1)


def validate_deployment_engine_release(
    configured_version: str,
    configured_generation: Optional[int] = None
) -> Tuple[str, int]:
    """
    Validates that a worker deployment's configured engine version and generation
    are recognized and mutually consistent with the authoritative release registry.

    Raises ValueError if:
    - The version is unknown.
    - The configured generation does not match the canonical generation for that version.
    """
    if configured_version not in MATCHING_ENGINE_RELEASES:
        raise ValueError(
            f"Incompatible worker engine release: '{configured_version}' is not registered in MATCHING_ENGINE_RELEASES."
        )

    canonical_gen = MATCHING_ENGINE_RELEASES[configured_version]
    if configured_generation is not None and configured_generation != canonical_gen:
        raise ValueError(
            f"Incompatible worker engine generation: configured generation {configured_generation} "
            f"does not match canonical generation {canonical_gen} for version '{configured_version}'."
        )

    return configured_version, canonical_gen

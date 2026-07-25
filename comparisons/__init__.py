"""Comparison framework for comparing Debian package versions against external sources."""

import json
import re
from abc import ABC, abstractmethod
from semver import Version


def parse_debian_upstream(version_str):
    """Extract upstream version from a Debian version string.

    Debian format: [epoch:]upstream[-debian_revision]
    Strips +dfsg, ~git, etc.
    """
    if not version_str:
        return None
    v = version_str
    if ":" in v:
        v = v.split(":", 1)[1]
    v = re.sub(r"-[\d.]+$", "", v)
    v = re.sub(r"\+.*$", "", v)
    v = re.sub(r"~.*$", "", v)
    return v


def to_semver(version_str):
    """Try to parse a version string into a semver.Version.

    Handles versions that aren't strictly semver:
    - Strips leading 'v'
    - Strips leading zeros from numeric components
    - Pads missing components
    - Strips pre-release/build noise
    """
    if not version_str:
        return None
    v = version_str.strip()
    v = re.sub(r"^v", "", v)

    def strip_leading_zero(m):
        s = m.group(0)
        if len(s) > 1 and s.startswith("0"):
            return str(int(s))
        return s

    v = re.sub(r"\b0+(\d+)\b", strip_leading_zero, v)
    try:
        return Version.parse(v)
    except ValueError:
        pass
    parts = v.split(".")
    if len(parts) == 1:
        v = f"{v}.0.0"
    elif len(parts) == 2:
        v = f"{v}.0"
    try:
        return Version.parse(v)
    except ValueError:
        pass
    v = re.sub(r"[-.](rc|alpha|beta|dev|pre|post)\d*$", "", v, flags=re.IGNORECASE)
    v = re.sub(r"[^+\-0-9.].*$", "", v)
    parts = v.split(".")
    if len(parts) == 2:
        v = f"{v}.0"
    try:
        return Version.parse(v)
    except ValueError:
        return None


def compute_version_delta(debian_upstream, other_upstream):
    """Compute how far ahead other is from Debian as a single number.

    Uses semver major/minor/patch distance: major*100 + minor*10 + patch.
    Returns None if can't compare, other is not newer, or versions are dates.
    """
    d = to_semver(debian_upstream)
    o = to_semver(other_upstream)
    if not d or not o:
        return None
    if o <= d:
        return None
    if d.major > 1900 or o.major > 1900:
        return None
    return (o.major - d.major) * 100 + (o.minor - d.minor) * 10 + (o.patch - d.patch)


class ComparisonSource(ABC):
    """Base class for version comparison sources."""

    @property
    @abstractmethod
    def name(self):
        """Human-readable name of the source (e.g. 'Arch Linux')."""
        pass

    @property
    @abstractmethod
    def slug(self):
        """Short identifier for the source (e.g. 'arch')."""
        pass

    @abstractmethod
    def fetch(self, cache_dir="data"):
        """Fetch version data from the source.

        Returns a dict of {package_name: version_string}.
        Should cache results in cache_dir.
        """
        pass

    def normalize_name(self, name):
        """Normalize a package name for matching.

        Override in subclasses for source-specific normalization.
        """
        return name

    def match_candidates(self, debian_source_name):
        """Generate candidate names to try when matching a Debian source package.

        Returns a list of names to try, in order of preference.
        Override for source-specific naming conventions.
        """
        return [
            debian_source_name,
            debian_source_name.replace("-", ""),
        ]

    def compare(self, debian_source_name, debian_version, packages_dict):
        """Compare a Debian package against this source.

        Returns a dict with comparison results, or None if no match found.
        """
        upstream = parse_debian_upstream(debian_version)
        if not upstream:
            return None

        other_version = None
        for candidate in self.match_candidates(debian_source_name):
            candidate_norm = self.normalize_name(candidate)
            if candidate_norm in packages_dict:
                other_version = packages_dict[candidate_norm]
                break

        if not other_version:
            return None

        delta = compute_version_delta(upstream, other_version)
        return {
            f"{self.slug}_version": other_version,
            f"{self.slug}_upstream_version": self.parse_upstream(other_version),
            "behind_upstream": delta is not None,
            "version_delta": delta,
        }

    @abstractmethod
    def parse_upstream(self, version_str):
        """Extract upstream version from this source's version string."""
        pass

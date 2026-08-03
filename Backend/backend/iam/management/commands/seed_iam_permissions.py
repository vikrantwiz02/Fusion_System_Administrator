"""Seed designation -> permission mappings from the platform's manifest.

    manage.py seed_iam_permissions --manifest .../registry/permissions.json

Idempotent, and authoritative only for the modules the manifest names: a grant
dropped upstream is revoked here, other modules are untouched.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from iam.models import RolePermission

SUPPORTED_VERSION = 1

#: Where the platform is deployed alongside this console.
DEFAULT_MANIFEST = Path("/srv/fusion/platform/current/registry/permissions.json")


class Command(BaseCommand):
    help = "Seed designation -> permission mappings from the platform manifest"

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest", type=Path, default=DEFAULT_MANIFEST,
            help=f"Path to registry/permissions.json (default {DEFAULT_MANIFEST})")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without writing.")

    def handle(self, *args, **opts):
        dry_run = opts["dry_run"]
        manifest = self._load(opts["manifest"])
        added, removed = self._apply(manifest, dry_run=dry_run)

        for line in removed:
            self.stdout.write(self.style.WARNING(
                f"  {'would revoke' if dry_run else 'revoked'} {line}"))
        self.stdout.write(self.style.SUCCESS(
            f"{len(added)} to add, {len(removed)} to revoke" if dry_run
            else f"{len(added)} added, {len(removed)} revoked; "
                 f"{RolePermission.objects.count()} total"))

    def _load(self, path: Path) -> dict:
        try:
            manifest = json.loads(path.read_text())
        except OSError as exc:
            raise CommandError(
                f"Cannot read {path}: {exc}. The platform writes it with "
                f"'make permissions'; pass --manifest if it lives elsewhere."
            ) from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f"{path} is not valid JSON: {exc}") from exc

        version = manifest.get("version")
        if version != SUPPORTED_VERSION:
            raise CommandError(
                f"{path} declares version {version!r}; this command "
                f"understands {SUPPORTED_VERSION}. Upgrade one side or the "
                f"other rather than guessing at the shape.")
        if not manifest.get("modules"):
            raise CommandError(f"{path} lists no modules — refusing to treat "
                               f"that as 'revoke everything'.")
        return manifest

    @transaction.atomic
    def _apply(self, manifest: dict, *, dry_run: bool):
        added, removed = [], []
        for module_code, spec in sorted(manifest["modules"].items()):
            wanted = {
                (designation, code)
                for designation, codes in spec.get("grants", {}).items()
                for code in codes
            }
            # Scoped to this module's prefix so another module's rows survive.
            existing = RolePermission.objects.filter(
                permission__startswith=f"{module_code}.")
            have = {(r.designation, r.permission) for r in existing}

            for designation, code in sorted(wanted - have):
                added.append(f"{designation}: {code}")
                if not dry_run:
                    RolePermission.objects.get_or_create(
                        designation=designation, permission=code)

            for designation, code in sorted(have - wanted):
                removed.append(f"{designation}: {code}")
                if not dry_run:
                    existing.filter(designation=designation,
                                    permission=code).delete()

            self.stdout.write(f"  {module_code}: {len(wanted)} mapping(s)")
        return added, removed

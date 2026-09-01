from django.apps import AppConfig


class IamConfig(AppConfig):
    name = "iam"
    verbose_name = "Identity & Access"

    def ready(self) -> None:
        # The ERP's tables are unmanaged, so the test database has none of them
        # and the suite could not start. Test-only, and a no-op otherwise.
        from iam.testing import install_for_tests

        install_for_tests()

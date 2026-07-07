from __future__ import annotations


class InstallerError(RuntimeError):
    pass


class InstallerUsageError(InstallerError):
    pass

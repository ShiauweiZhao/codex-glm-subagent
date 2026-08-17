"""Native macOS Keychain credential storage for codex-glm-subagent.

Uses the Security and CoreFoundation frameworks directly via ctypes with the
legacy generic-password API. The secret never appears in a command line.
"""

import argparse
import ctypes
import getpass as _getpass
import platform as _platform
import sys

KEYCHAIN_SERVICE = "com.shiauweizhao.codex-glm-subagent"
API_KEY_ACCOUNT = "zai-api-key"

_ERR_SEC_SUCCESS = 0
_ERR_SEC_ITEM_NOT_FOUND = -25300

_NON_DARWIN_MSG = (
    "Native macOS Keychain is not available on this platform. "
    "Set ZAI_API_KEY for Codex provider auth."
)


class _MacOSKeychainBackend:
    """Exact generic-password get/put/delete through native frameworks."""

    NOT_FOUND = _ERR_SEC_ITEM_NOT_FOUND

    def __init__(self):
        self.security = ctypes.CDLL(
            "/System/Library/Frameworks/Security.framework/Security"
        )
        self.core_foundation = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
        self._configure_signatures()

    def _configure_signatures(self):
        sec = self.security
        sec.SecKeychainFindGenericPassword.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        sec.SecKeychainFindGenericPassword.restype = ctypes.c_int32
        sec.SecKeychainAddGenericPassword.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_char_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        sec.SecKeychainAddGenericPassword.restype = ctypes.c_int32
        sec.SecKeychainItemModifyAttributesAndData.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        sec.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
        sec.SecKeychainItemDelete.argtypes = [ctypes.c_void_p]
        sec.SecKeychainItemDelete.restype = ctypes.c_int32
        sec.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        sec.SecKeychainItemFreeContent.restype = ctypes.c_int32
        self.core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
        self.core_foundation.CFRelease.restype = None

    def _find(self):
        service = KEYCHAIN_SERVICE.encode("utf-8")
        account_bytes = API_KEY_ACCOUNT.encode("utf-8")
        password_length = ctypes.c_uint32()
        password_data = ctypes.c_void_p()
        item = ctypes.c_void_p()
        status = self.security.SecKeychainFindGenericPassword(
            None,
            len(service),
            service,
            len(account_bytes),
            account_bytes,
            ctypes.byref(password_length),
            ctypes.byref(password_data),
            ctypes.byref(item),
        )
        value = None
        if status == _ERR_SEC_SUCCESS:
            value = ctypes.string_at(password_data, password_length.value)
        if password_data:
            self.security.SecKeychainItemFreeContent(None, password_data)
        return status, value, item

    def get(self):
        status, value, item = self._find()
        try:
            if status == self.NOT_FOUND:
                return None
            if status != _ERR_SEC_SUCCESS or value is None:
                raise RuntimeError(f"Keychain read failed with OSStatus {status}")
            return value.decode("utf-8")
        finally:
            if item:
                self.core_foundation.CFRelease(item)

    def put(self, secret):
        if not isinstance(secret, str) or not secret:
            raise ValueError("secret must be a non-empty string")
        status, _value, item = self._find()
        secret_bytes = secret.encode("utf-8")
        secret_buffer = ctypes.create_string_buffer(secret_bytes)
        try:
            if status == _ERR_SEC_SUCCESS:
                update_status = self.security.SecKeychainItemModifyAttributesAndData(
                    item,
                    None,
                    len(secret_bytes),
                    ctypes.cast(secret_buffer, ctypes.c_void_p),
                )
            elif status == self.NOT_FOUND:
                service = KEYCHAIN_SERVICE.encode("utf-8")
                account_bytes = API_KEY_ACCOUNT.encode("utf-8")
                created_item = ctypes.c_void_p()
                update_status = self.security.SecKeychainAddGenericPassword(
                    None,
                    len(service),
                    service,
                    len(account_bytes),
                    account_bytes,
                    len(secret_bytes),
                    ctypes.cast(secret_buffer, ctypes.c_void_p),
                    ctypes.byref(created_item),
                )
                if created_item:
                    self.core_foundation.CFRelease(created_item)
            else:
                raise RuntimeError(f"Keychain lookup failed with OSStatus {status}")
            if update_status != _ERR_SEC_SUCCESS:
                raise RuntimeError(
                    f"Keychain update failed with OSStatus {update_status}"
                )
        finally:
            ctypes.memset(secret_buffer, 0, len(secret_buffer))
            if item:
                self.core_foundation.CFRelease(item)

    def delete(self):
        status, _value, item = self._find()
        try:
            if status == self.NOT_FOUND:
                return
            if status != _ERR_SEC_SUCCESS:
                raise RuntimeError(f"Keychain lookup failed with OSStatus {status}")
            delete_status = self.security.SecKeychainItemDelete(item)
            if delete_status != _ERR_SEC_SUCCESS:
                raise RuntimeError(
                    f"Keychain delete failed with OSStatus {delete_status}"
                )
        finally:
            if item:
                self.core_foundation.CFRelease(item)


class KeychainStore:
    """Wrapper that maps backend failures to generic redacted RuntimeErrors."""

    def __init__(self, backend=None):
        self._backend = backend if backend is not None else _MacOSKeychainBackend()

    def get(self):
        try:
            return self._backend.get()
        except Exception:  # noqa: BLE001
            raise RuntimeError(
                f"could not read Keychain item '{API_KEY_ACCOUNT}'"
            ) from None

    def put(self, secret):
        try:
            self._backend.put(secret)
        except Exception:  # noqa: BLE001
            raise RuntimeError(
                f"could not update Keychain item '{API_KEY_ACCOUNT}'"
            ) from None

    def delete(self):
        try:
            self._backend.delete()
        except Exception:  # noqa: BLE001
            raise RuntimeError(
                f"could not delete Keychain item '{API_KEY_ACCOUNT}'"
            ) from None


def _is_darwin(platform_module):
    return platform_module.system() == "Darwin"


def _cmd_configure(args, getpass_module, stdout, stderr, store_factory):
    secret = getpass_module.getpass("Enter ZAI API key: ")
    if not secret:
        print("API key must not be empty.", file=stderr)
        return 2
    store_factory().put(secret)
    print(f"Stored API key for account {API_KEY_ACCOUNT} in Keychain.", file=stdout)
    return 0


def _cmd_print_api_key(stdout, stderr, store_factory):
    secret = store_factory().get()
    if secret is None:
        print("API key not found in Keychain.", file=stderr)
        return 1
    if isinstance(secret, bytes):
        secret = secret.decode("utf-8")
    stdout.write(secret)
    return 0


def _cmd_status(stdout, store_factory):
    if store_factory().get() is None:
        print("API key is not configured.", file=stdout)
    else:
        print("API key is configured.", file=stdout)
    return 0


def _cmd_purge(stdout, store_factory):
    store_factory().delete()
    print("API key removed from Keychain.", file=stdout)
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(prog="codex-glm-subagent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("configure", help="store the ZAI API key")
    subparsers.add_parser("print-api-key", help="print the stored key to stdout")
    subparsers.add_parser("status", help="report whether a key is configured")
    subparsers.add_parser("purge", help="remove the stored key")
    return parser


def main(
    argv=None,
    *,
    getpass_module=None,
    platform_module=None,
    stdout=None,
    stderr=None,
    store_factory=None,
):
    argv = sys.argv[1:] if argv is None else argv
    getpass_module = getpass_module or _getpass
    platform_module = platform_module or _platform
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    store_factory = store_factory or KeychainStore
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not _is_darwin(platform_module):
        print(_NON_DARWIN_MSG, file=stderr)
        return 2
    if args.command == "configure":
        return _cmd_configure(args, getpass_module, stdout, stderr, store_factory)
    if args.command == "print-api-key":
        return _cmd_print_api_key(stdout, stderr, store_factory)
    if args.command == "status":
        return _cmd_status(stdout, store_factory)
    if args.command == "purge":
        return _cmd_purge(stdout, store_factory)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

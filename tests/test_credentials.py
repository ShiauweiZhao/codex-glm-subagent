import inspect
import io
import sys
import unittest

from codex_glm53_subagent import credentials as cred_module
from codex_glm53_subagent.credentials import (
    API_KEY_ACCOUNT,
    KEYCHAIN_SERVICE,
    KeychainStore,
    _MacOSKeychainBackend,
    main,
)

_CREDENTIALS_SOURCE = inspect.getsource(cred_module)


class _FakeBackend:
    def __init__(self, secret=None, fail=None):
        self.secret = secret
        self.fail = fail
        self.put_calls = []
        self.delete_calls = 0

    def get(self):
        if self.fail:
            raise self.fail
        return self.secret

    def put(self, secret):
        self.put_calls.append(secret)
        if self.fail:
            raise self.fail

    def delete(self):
        self.delete_calls += 1
        if self.fail:
            raise self.fail


class _FakeGetpass:
    def __init__(self, value=None):
        self.value = value
        self.prompts = []

    def getpass(self, prompt=""):
        self.prompts.append(prompt)
        return self.value


class _FakePlatform:
    def __init__(self, system="Darwin"):
        self._system = system

    def system(self):
        return self._system


def _store(backend):
    return lambda: KeychainStore(backend=backend)


class SourceAuditTest(unittest.TestCase):
    def test_no_secitem(self):
        self.assertNotIn("SecItem", _CREDENTIALS_SOURCE)

    def test_no_cfdictionary(self):
        self.assertNotIn("CFDictionary", _CREDENTIALS_SOURCE)

    def test_no_boolean_sentinel(self):
        self.assertNotIn("_KCF_BOOLEAN_TRUE", _CREDENTIALS_SOURCE)

    def test_no_subprocess(self):
        self.assertNotIn("subprocess", _CREDENTIALS_SOURCE)


class ConstantsTest(unittest.TestCase):
    def test_keychain_service_constant(self):
        self.assertEqual(KEYCHAIN_SERVICE, "com.shiauweizhao.codex-glm-subagent")

    def test_api_key_account_constant(self):
        self.assertEqual(API_KEY_ACCOUNT, "zai-api-key")


class ConfigureCommandTest(unittest.TestCase):
    def test_configure_stores_exact_account_and_prints_no_secret(self):
        backend = _FakeBackend()
        out = io.StringIO()
        err = io.StringIO()
        getpass = _FakeGetpass("s3cr3t-value")
        rc = main(
            ["configure"],
            getpass_module=getpass,
            platform_module=_FakePlatform("Darwin"),
            stdout=out,
            stderr=err,
            store_factory=_store(backend),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(backend.put_calls, ["s3cr3t-value"])
        self.assertNotIn("s3cr3t-value", out.getvalue())
        self.assertIn(API_KEY_ACCOUNT, out.getvalue())

    def test_configure_rejects_empty_secret(self):
        backend = _FakeBackend()
        out = io.StringIO()
        err = io.StringIO()
        rc = main(
            ["configure"],
            getpass_module=_FakeGetpass(""),
            platform_module=_FakePlatform("Darwin"),
            stdout=out,
            stderr=err,
            store_factory=_store(backend),
        )
        self.assertEqual(rc, 2)
        self.assertEqual(backend.put_calls, [])


class PrintApiKeyCommandTest(unittest.TestCase):
    def test_print_api_key_writes_only_secret(self):
        backend = _FakeBackend(secret=b"sk-live-secret")
        out = io.StringIO()
        err = io.StringIO()
        rc = main(
            ["print-api-key"],
            platform_module=_FakePlatform("Darwin"),
            stdout=out,
            stderr=err,
            store_factory=_store(backend),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "sk-live-secret")

    def test_print_api_key_absent_returns_clean_error(self):
        backend = _FakeBackend(secret=None)
        out = io.StringIO()
        err = io.StringIO()
        rc = main(
            ["print-api-key"],
            platform_module=_FakePlatform("Darwin"),
            stdout=out,
            stderr=err,
            store_factory=_store(backend),
        )
        self.assertEqual(rc, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("not found", err.getvalue())


class StatusCommandTest(unittest.TestCase):
    def test_status_configured(self):
        backend = _FakeBackend(secret=b"x")
        out = io.StringIO()
        rc = main(
            ["status"],
            platform_module=_FakePlatform("Darwin"),
            stdout=out,
            stderr=io.StringIO(),
            store_factory=_store(backend),
        )
        self.assertEqual(rc, 0)
        self.assertIn("configured", out.getvalue().lower())
        self.assertNotIn("x", out.getvalue())

    def test_status_not_configured(self):
        backend = _FakeBackend(secret=None)
        out = io.StringIO()
        rc = main(
            ["status"],
            platform_module=_FakePlatform("Darwin"),
            stdout=out,
            stderr=io.StringIO(),
            store_factory=_store(backend),
        )
        self.assertEqual(rc, 0)
        self.assertIn("not configured", out.getvalue().lower())


class PurgeCommandTest(unittest.TestCase):
    def test_purge_deletes_exact_account(self):
        backend = _FakeBackend()
        out = io.StringIO()
        rc = main(
            ["purge"],
            platform_module=_FakePlatform("Darwin"),
            stdout=out,
            stderr=io.StringIO(),
            store_factory=_store(backend),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(backend.delete_calls, 1)

    def test_purge_is_idempotent(self):
        backend = _FakeBackend()
        out = io.StringIO()
        for _ in range(2):
            rc = main(
                ["purge"],
                platform_module=_FakePlatform("Darwin"),
                stdout=out,
                stderr=io.StringIO(),
                store_factory=_store(backend),
            )
            self.assertEqual(rc, 0)
        self.assertEqual(backend.delete_calls, 2)


class NonDarwinTest(unittest.TestCase):
    def test_non_darwin_tells_user_and_never_touches_backend(self):
        for command in ("configure", "print-api-key", "status", "purge"):
            backend = _FakeBackend(secret=b"must-not-leak")
            out = io.StringIO()
            err = io.StringIO()
            getpass = _FakeGetpass("should-not-be-read")
            rc = main(
                [command],
                getpass_module=getpass,
                platform_module=_FakePlatform("Linux"),
                stdout=out,
                stderr=err,
                store_factory=_store(backend),
            )
            self.assertEqual(rc, 2, command)
            self.assertIn("ZAI_API_KEY", err.getvalue(), command)
            self.assertEqual(backend.put_calls, [], command)
            self.assertEqual(backend.delete_calls, 0, command)
            self.assertEqual(getpass.prompts, [], command)
            self.assertNotIn("must-not-leak", out.getvalue(), command)


class KeychainStoreTest(unittest.TestCase):
    def test_put_failure_is_generic_and_redacted(self):
        secret = "super-secret-value"
        backend = _FakeBackend(fail=RuntimeError("boom: super-secret-value"))
        store = KeychainStore(backend=backend)
        with self.assertRaises(RuntimeError) as ctx:
            store.put(secret)
        msg = str(ctx.exception)
        self.assertNotIn(secret, msg)
        self.assertNotIn("boom", msg)
        self.assertIn("could not update Keychain item", msg)
        self.assertIn(API_KEY_ACCOUNT, msg)
        self.assertIsNone(ctx.exception.__cause__)

    def test_get_failure_is_generic_and_redacted(self):
        backend = _FakeBackend(fail=OSError("boom: keychain read failed"))
        store = KeychainStore(backend=backend)
        with self.assertRaises(RuntimeError) as ctx:
            store.get()
        msg = str(ctx.exception)
        self.assertNotIn("boom", msg)
        self.assertIn("could not read Keychain item", msg)
        self.assertIn(API_KEY_ACCOUNT, msg)
        self.assertIsNone(ctx.exception.__cause__)

    def test_delete_failure_is_generic_and_redacted(self):
        backend = _FakeBackend(fail=OSError("boom: keychain delete failed"))
        store = KeychainStore(backend=backend)
        with self.assertRaises(RuntimeError) as ctx:
            store.delete()
        msg = str(ctx.exception)
        self.assertNotIn("boom", msg)
        self.assertIn("could not delete Keychain item", msg)
        self.assertIn(API_KEY_ACCOUNT, msg)
        self.assertIsNone(ctx.exception.__cause__)

    def test_get_returns_utf8_string(self):
        store = KeychainStore(backend=_FakeBackend(secret="abc"))
        value = store.get()
        self.assertEqual(value, "abc")
        self.assertIsInstance(value, str)

    def test_get_absent_returns_none(self):
        store = KeychainStore(backend=_FakeBackend(secret=None))
        self.assertIsNone(store.get())


@unittest.skipUnless(sys.platform == "darwin", "macOS-only backend")
class RealBackendValidationTest(unittest.TestCase):
    def test_put_rejects_empty_and_non_string(self):
        backend = _MacOSKeychainBackend()
        with self.assertRaises(ValueError):
            backend.put("")
        with self.assertRaises(ValueError):
            backend.put(123)


if __name__ == "__main__":
    unittest.main()

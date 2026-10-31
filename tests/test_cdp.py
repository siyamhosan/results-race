"""The browser connection: losing it is fatal (so a supervisor restarts us), closing it on purpose is not."""
import asyncio
import unittest
from unittest import mock

from results_race.cdp import Browser


class EmptyConnection:
    """A websocket that closes straight away, like a browser that has died."""
    close_code, close_reason = 1006, ""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class HangingConnection:
    """A connection that is simply quiet: nothing arrives, nothing closes."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.Event().wait()


def browser():
    b = Browser()
    b.ws, b.waiters, b.listeners = EmptyConnection(), {}, {}
    b.proc = mock.Mock()
    b.proc.poll.return_value = None  # the process is still running when the connection drops
    return b


class ConnectionTest(unittest.IsolatedAsyncioTestCase):
    async def test_a_lost_browser_ends_the_app_with_an_error_exit(self):
        with mock.patch("results_race.cdp.os._exit") as exit_:
            b = browser()
            await b._read()
        exit_.assert_called_once_with(1)
        b.proc.terminate.assert_called_once()  # os._exit skips atexit: the browser must be stopped first

    async def test_closing_it_on_purpose_does_not(self):
        b = browser()
        b.closing = True
        with mock.patch("results_race.cdp.os._exit") as exit_:
            await b._read()
        exit_.assert_not_called()

    async def test_being_cancelled_at_shutdown_is_not_a_lost_browser(self):
        b = browser()
        b.ws = HangingConnection()
        task = asyncio.create_task(b._read())
        await asyncio.sleep(0.01)
        with mock.patch("results_race.cdp.os._exit") as exit_:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        exit_.assert_not_called()

    async def test_close_marks_it_so_the_reader_stays_quiet(self):
        b = browser()
        b.proc = mock.Mock()
        b.profile = "/nonexistent-profile"
        b.close_ws = None
        await b.close()
        self.assertTrue(b.closing)


unittest.main() if __name__ == "__main__" else None

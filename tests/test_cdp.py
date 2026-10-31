"""The browser connection: losing it is fatal (so a supervisor restarts us), closing it on purpose is not."""
import asyncio
import unittest
from unittest import mock

from results_race.cdp import Browser


class EmptyConnection:
    """A websocket that closes straight away, like a browser that has died."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


def browser():
    b = Browser()
    b.ws, b.waiters, b.listeners = EmptyConnection(), {}, {}
    return b


class ConnectionTest(unittest.IsolatedAsyncioTestCase):
    async def test_a_lost_browser_ends_the_app_with_an_error_exit(self):
        with mock.patch("results_race.cdp.os._exit") as exit_:
            await browser()._read()
        exit_.assert_called_once_with(1)

    async def test_closing_it_on_purpose_does_not(self):
        b = browser()
        b.closing = True
        with mock.patch("results_race.cdp.os._exit") as exit_:
            await b._read()
        exit_.assert_not_called()

    async def test_close_marks_it_so_the_reader_stays_quiet(self):
        b = browser()
        b.proc = mock.Mock()
        b.profile = "/nonexistent-profile"
        b.close_ws = None
        await b.close()
        self.assertTrue(b.closing)


unittest.main() if __name__ == "__main__" else None

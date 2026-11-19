#!/usr/bin/env python3
"""Take the campaign's command lock where there is no `flock` program (macOS).

tools/common.sh keeps the lock file open on descriptor 9 and normally locks it
with `flock`. This does the same through Python: the lock belongs to the open
file, which this process shares with the wrapper that started it, so the lock
stays with the wrapper when this process ends.

    command_lock.py <seconds to wait>     exit 0: locked; 1: still taken
"""

import fcntl
import sys
import time

DESCRIPTOR = 9


def take(seconds: float, descriptor: int = DESCRIPTOR) -> bool:
    """Lock the file open on `descriptor`, waiting up to `seconds` for whoever has it."""
    end = time.time() + seconds
    while True:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.time() >= end:
                return False
            time.sleep(0.05)


if __name__ == "__main__":
    sys.exit(0 if take(float(sys.argv[1]) if sys.argv[1:] else 30) else 1)

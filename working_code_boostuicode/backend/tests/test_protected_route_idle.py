import time

THIRTY_SECONDS = 30  # seconds (test mode)

class LocalStorageSim:
    def __init__(self):
        self.store = {}
    def get(self, key):
        return self.store.get(key)
    def set(self, key, value):
        self.store[key] = value
    def remove(self, key):
        if key in self.store:
            del self.store[key]
    def clear(self):
        self.store.clear()

# Simulated actions
ls = LocalStorageSim()

def update_last_activity():
    ls.set('lastActivity', str(int(time.time() * 1000)))

def check_on_mount():
    last = ls.get('lastActivity')
    if not last:
        return True  # no timestamp, consider active (or decide to logout on missing token elsewhere)
    elapsed_ms = int(time.time() * 1000) - int(last)
    return elapsed_ms <= THIRTY_SECONDS * 1000

# Helpers for tests

def scenario_fresh_activity():
    print('\nScenario: fresh activity, should be ACTIVE')
    update_last_activity()
    print('lastActivity (ms):', ls.get('lastActivity'))
    time.sleep(2)
    ok = check_on_mount()
    print('check_on_mount ->', 'ACTIVE' if ok else 'EXPIRED')


def scenario_expired_activity():
    print('\nScenario: last activity older than TTL, should be EXPIRED')
    # set lastActivity to now - (THIRTY_SECONDS + 5)
    past = int((time.time() - (THIRTY_SECONDS + 5)) * 1000)
    ls.set('lastActivity', str(past))
    print('lastActivity (ms):', ls.get('lastActivity'))
    ok = check_on_mount()
    print('check_on_mount ->', 'ACTIVE' if ok else 'EXPIRED')


def scenario_close_and_reopen_delay(delay_seconds):
    print(f'\nScenario: close tab, wait {delay_seconds}s, reopen -> expect EXPIRED if delay > {THIRTY_SECONDS}')
    update_last_activity()
    print('set lastActivity to now')
    # simulate close (nothing to do) and wait
    time.sleep(delay_seconds)
    ok = check_on_mount()
    print('check_on_mount after reopen ->', 'ACTIVE' if ok else 'EXPIRED')


if __name__ == '__main__':
    print('Starting ProtectedRoute idle simulation tests (TTL =', THIRTY_SECONDS, 'seconds)')
    scenario_fresh_activity()
    scenario_expired_activity()
    # quick test: wait 31s to simulate reopen after TTL
    scenario_close_and_reopen_delay(31)

    print('\nAll tests completed.')

import time

from rate_limit import RateLimiter, TokenBucket


def test_rate_limiter_ready():
    limiter = RateLimiter(0.01)
    assert limiter.ready()
    limiter.wait()
    assert not limiter.ready()


def test_token_bucket():
    bucket = TokenBucket(rate=100, capacity=2)
    assert bucket.allow()
    assert bucket.allow()
    assert not bucket.allow()
    time.sleep(0.02)
    assert bucket.allow()


if __name__ == "__main__":
    test_rate_limiter_ready()
    test_token_bucket()
    print("test_rate_limit ok")

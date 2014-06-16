from contextlib import contextmanager


@contextmanager
def cleanup_on_failure(deployment):
    try:
        yield
    except (Exception, KeyboardInterrupt):
        deployment.destroy()

import logging
from contextlib import contextmanager
import monster.active as active

logger = logging.getLogger(__name__)


@contextmanager
def cleanup_on_failure(deployment):
    try:
        yield
    except (Exception, KeyboardInterrupt) as e:
        if active.build_args['destroy_on_failure']:
            logger.info("build failed; deleting partially-built servers...")
            deployment.destroy()
        raise e

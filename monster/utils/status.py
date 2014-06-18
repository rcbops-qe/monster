from monster import db_iface as database, active
from monster.provisioners.rackspace import provisioner as rackspace
from monster.utils.access import check_port
import logging

logger = logging.getLogger(__name__)


def check_monster_status():
    try:
        database.ping_db()
    except AssertionError:
        logger.warning("Database is not responding normally...")
        raise
    else:
        logger.info("Database is up!")

    try:
        rackspace.Provisioner()
    except Exception:
        logger.warning("Rackspace credentials did not authenticate.")
        raise
    else:
        logger.info("Rackspace credentials look good!")
    try:
        razor_ip = active.config['secrets']['razor']['ip']
        check_port(host=razor_ip, port=8026, attempts=1)
    except KeyError:
        logger.info("No razor IP specified; Razor provisioner will not be "
                    "available.")
    except Exception:
        logger.warning("Specified Razor host did not seem responsive on port "
                       "8026. Razor provisioner will likely be unavailable.")
    else:
        logger.info("Razor host is up and responding on port 8026!")

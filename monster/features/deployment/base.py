from weakref import proxy
from monster.features import base as base


class Feature(base.Feature):
    """Represents a feature across a deployment."""

    def __init__(self, deployment, rpcs_feature):
        self.rpcs_feature = rpcs_feature
        self.deployment = proxy(deployment)

    def __repr__(self):
        return 'class: ' + self.__class__.__name__

    @property
    def to_dict(self):
        return {str(self).lower(): self.rpcs_feature}

    def update_environment(self):
        pass

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass

"""Base feature."""


class Feature(object):
    def __repr__(self):
        return 'class: ' + self.__class__.__name__

    def __str__(self):
        """Prints out class name in lower case.
        :rtype: str
        """
        return self.__class__.__name__.lower()

    def update_environment(self):
        pass

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass

    def destroy(self):
        pass

    def archive(self):
        pass

""" Base Feature """


class Feature(object):
    """
    Represents a OpenStack Feature
    """

    def __repr__(self):
        """Prints out current instance.
        :rtype: String
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def __str__(self):
        """Prints out class name.
        :rtype: String
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

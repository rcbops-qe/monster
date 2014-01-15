"""
Base environment
"""


class Environment(dict):

    def __init__(self, name, description):
        self.name = name
        self.description = description

    def __repr__(self):
        """ 
        Print out current instance
        """
        
        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))
        return outl

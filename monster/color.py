class Color:
    @classmethod
    def cyan(cls, string):
        return '%s%s%s' % ('\033[1;36m', string, '\033[1;m')

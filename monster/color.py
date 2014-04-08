class Color:
    @classmethod
    def red(cls, string):
        return "{0}{1}{2}".format('\033[1;31m', string, '\033[0m')

    @classmethod
    def cyan(cls, string):
        return "{0}{1}{2}".format('\033[1;36m', string, '\033[0m')

    @classmethod
    def blue(cls, string):
        return "{0}{1}{2}".format('\033[1;34m', string, '\033[0m')

    @classmethod
    def yellow(cls, string):
        return "{0}{1}{2}".format('\033[1;33m', string, '\033[0m')

    @classmethod
    def gray(cls, string):
        return "{0}{1}{2}".format('\033[1;90m', string, '\033[0m')

    @classmethod
    def green(cls, string):
        return "{0}{1}{2}".format('\033[1;92m', string, '\033[0m')

    @classmethod
    def blink(cls, string):
        return "{0}{1}{2}".format('\033[1;5m', string, '\033[0m')

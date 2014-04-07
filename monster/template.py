class Template:
    """
    A wrapper class for the template dict
    """
    def __init__(self, template_dict):
        self.template_dict = template_dict

    def __getitem__(self, item):
        return self.template_dict[item]

    def fetch(self, *args):
        """
        Takes a series of keys and returns their values from the template
        :param args:
        :return:
        """
        return tuple([self.template_dict[x] for x in args])

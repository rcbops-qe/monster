import sys
from monster.upgrades import *


# Borrowed from vegaseat
# http://www.daniweb.com/software-development/
# python/code/216839/number-to-word-converter-python
from monster.utils.introspection import module_classes


def int2word(n):
    """
    convert an integer number n into a string of english words
    """
    # break the number into groups of 3 digits using slicing
    # each group representing hundred, thousand, million, billion, ...
    n3 = []
    # create numeric string
    ns = str(n)
    for k in range(3, 33, 3):
        r = ns[-k:]
        q = len(ns) - k
        # break if end of ns has been reached
        if q < -2:
            break
        else:
            if q >= 0:
                n3.append(int(r[:3]))
            elif q >= -1:
                n3.append(int(r[:2]))
            elif q >= -2:
                n3.append(int(r[:1]))
    # break each group of 3 digits into
    # ones, tens/twenties, hundreds
    # and form a string
    nw = ""
    for i, x in enumerate(n3):
        b1 = x % 10
        b2 = (x % 100) // 10
        b3 = (x % 1000) // 100
        #print b1, b2, b3  # test
        if x == 0:
            continue  # skip
        else:
            t = thousands[i]
        if b2 == 0:
            nw = ones[b1] + t + nw
        elif b2 == 1:
            nw = tens[b1] + t + nw
        elif b2 > 1:
            nw = twenties[b2] + ones[b1] + t + nw
        if b3 > 0:
            nw = ones[b3] + "hundred " + nw
    return nw


def get_upgrade(deployment, branch_name):
    """This will return an instance of the correct upgrade class.
    :param branch_name: The name of the provisioner
    :type branch_name: str
    :rtype: monster.deployments.base.Deployment
    """

    # convert branch into a list of int strings
    word_b = [int2word(int(numeral))
              for numeral in
              branch_name.rstrip('rc').lstrip('v').split('.')]

    # convert list to class name
    up_class = "".join(word_b).replace(" ", "")
    up_class_module = "_".join(word_b).replace(" ", "")

    try:
        identifier = getattr(sys.modules['monster'].upgrades,
                             up_class_module)
    except AttributeError:
        raise NameError("{0} doesn't exist.".format(up_class_module))
    return module_classes(identifier)[up_class](deployment)


############# globals ################
ones = ["", "one ", "two ", "three ", "four ", "five ",
        "six ", "seven ", "eight ", "nine "]
tens = ["ten ", "eleven ", "twelve ", "thirteen ", "fourteen ",
        "fifteen ", "sixteen ", "seventeen ", "eighteen ", "nineteen "]
twenties = ["", "", "twenty ", "thirty ", "forty ",
            "fifty ", "sixty ", "seventy ", "eighty ", "ninety "]
thousands = ["", "thousand ", "million ", "billion ", "trillion ",
             "quadrillion ", "quintillion ", "sextillion ", "septillion ",
             "octillion ", "nonillion ", "decillion ", "undecillion ",
             "duodecillion ", "tredecillion ", "quattuordecillion ",
             "sexdecillion ", "septendecillion ", "octodecillion ",
             "novemdecillion ", "vigintillion "]

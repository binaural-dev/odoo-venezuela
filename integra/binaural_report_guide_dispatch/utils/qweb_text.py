import math


def round_up(num):
    if num - int(num) >= 0.5:
        return math.ceil(num)
    else:
        return int(num)


def encode_text(text):
    return str(text).replace('"', "").replace("ñ", "n").replace("Ñ", "N").encode("latin-1")


def get_spaces(string1, string2, max_char_line, type_a=False):
    char = max_char_line if not type_a else 48
    len_char = char - len(string1) - len(string2)
    spaces = "".join([" " for x in range(len_char)])
    return string1 + spaces + string2

def get_count_spaces(lst):
    return len([val for pair in ['0'] * len(lst) for val in pair][:-1])

def get_multi_spaces(list_string, max_char_line, type_a=False):
    char = 48 if type_a else max_char_line
    len_char = char - sum([len(string) for string in list_string])
    len_spaces = round(len_char / get_count_spaces(list_string))

    if len_spaces - int(len_spaces) >= 0.5:
        len_spaces += 1

    space = "".join([" " for x in range(int(len_spaces))])

    return space.join(list_string)

def vef_amount_format(number):
    return "{0:,.2f}".format(number).replace(',','&').replace('.', '*').replace('&','.').replace('*',',')
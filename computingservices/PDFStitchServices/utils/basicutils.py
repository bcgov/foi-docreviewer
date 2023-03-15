def add_spacing_around_special_character(special_char, stringvalue):
    string= stringvalue.split(special_char)
    return f' {special_char} '.join(string)
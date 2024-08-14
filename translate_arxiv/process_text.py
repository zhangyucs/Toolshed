charLimit = 2000


def is_connected(lineAbove, lineBelow):
    if len(lineAbove) > 0 and len(lineBelow) > 0:
        if lineAbove[-1] != '.' and lineBelow[0].islower():
            return True
    return False


def connect_paragraphs(text):
    textSplit = text.split('\n')
    i = 0
    while i < len(textSplit) - 1:
        lineAbove = textSplit[i]
        lineBelow = textSplit[i + 1]
        if is_connected(lineAbove, lineBelow):
            textSplit[i] = textSplit[i] + textSplit[i + 1]
            del textSplit[i + 1]
        else:
            i += 1
    return '\n'.join(textSplit)


def get_first_word(line):
    words = line.split(' ')
    for word in words:
        if len(word) > 0:
            return word
    return ''


def argmax(array):
    return array.index(max(array))


def split_too_long_paragraphs(text):
    textSplit = []
    for paragraph in text.split('\n'):
        if len(paragraph) > charLimit:
            lines = paragraph.split('.')
            firstWords = [get_first_word(line) for line in lines]
            firstLength = [len(word) if (len(word) > 0 and word[0].isupper()) else 0 for word in firstWords]
            firstLength[0] = 0
            position = argmax(firstLength)
            par1 = split_too_long_paragraphs('.'.join(lines[0:position]) + '.')
            par2 = split_too_long_paragraphs('.'.join(lines[position:]))
            textSplit.extend([par1, par2])
        else:
            textSplit.append(paragraph)
    return '\n'.join(textSplit)


def is_title(lineAbove, lineBelow):
    if len(lineAbove) > 0 and len(lineBelow) > 0:
        if lineAbove[-1] != '.' and (not lineAbove[0].islower()) and lineBelow[0].isupper():
            return True
    return False


def split_titles(text):
    textSplit = text.split('\n')
    i = 0
    while i < len(textSplit) - 1:
        line_above = textSplit[i]
        line_below = textSplit[i + 1]
        if is_title(line_above, line_below):
            textSplit[i] = '\n\n' + textSplit[i] + '\n\n'
        i += 1
    return '\n'.join(textSplit)
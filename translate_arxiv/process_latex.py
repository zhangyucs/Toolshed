import re
import regex
from config import config


mathCode = config.math_code
testEnvironment = config.test_environment

matchCode = r"(" + mathCode + r"_\d+(?:_\d+)*)"
matchCodeReplace = mathCode + r"_(\d+(?:_\d+)*)*"

#options = r"\[[a-zA-Z\s,\\\*\.\+\-=_{}\(\)\!]*?\]"  # ,\*.+-=_{}!
options = r"\[[^\[\]]*?\]"
spaces = r"[ \t]*"

getPatternBrace = lambda index: rf"\{{((?:[^{{}}]++|(?{index}))*+)\}}"
getPatternEnv = lambda name: rf"\\begin{spaces}\{{({name})\}}{spaces}({options})?(.*?)\\end{spaces}\{{\1\}}"


def get_pattern_command_full(name, n=None):
    pattern = rf'\\({name})'
    if n is None:
        pattern += rf'{spaces}({options})?'
        n = 1
        beginBrace = 3
    else:
        beginBrace = 2
    for i in range(n):
        tmp = getPatternBrace(i*2+beginBrace)
        pattern += rf'{spaces}({tmp})'
    if n == 0:
        pattern += r'(?=[^a-zA-Z])'
    return pattern


matchCommandName = r'[a-zA-Z]+\*?'

patternEnv = getPatternEnv(r'.*?')  # \begin{xxx} \end{xxx}, group 1: name, group 2: option, group 3: content
patternCommandFull = get_pattern_command_full(matchCommandName)   # \xxx[xxx]{xxx} and \xxx{xxx}, group 1: name, group 2: option, group 4: content
patternCommandSimple = rf'\\({matchCommandName})'  # \xxx, group 1: name
patternBrace = getPatternBrace(0)  # {xxx}, group 1: content
patternNewcommand = rf'\\(?:newcommand|def){spaces}(?:\{{\\([a-zA-Z]+)\}}|\\([a-zA-Z]+)){spaces}(?:\[(\d)\])?{spaces}({getPatternBrace(4)})'  # \newcommand{name}[n_arguments]{content}, group 1/2: name, group 3: n_arguments, group 5: content

patternSet1 = rf'\\set[a-zA-Z]*{spaces}\\[a-zA-Z]+{spaces}\{{.*?\}}'
patternSet2 = rf'\\set[a-zA-Z]*{spaces}\{{\\[a-zA-Z]+\}}{spaces}\{{.*?\}}'
patternTheorem = r"\\newtheorem[ \t]*\{(.+?)\}"  # \newtheorem{xxx}, group 1: name
patternAccent = r"\\([`'\"^~=.])(?:\{([a-zA-Z])\}|([a-zA-Z]))"  # match special characters with accents, group 1: accent, group 2/3: normal character
matchCodeAccent = rf'{mathCode}([A-Z]{{2}})([a-zA-Z])'  # group 1: accent name, group 2: normal character, e.g. \"o or \"{o}
listSpecial = ['\\', '%', '&', '#', '$', '{', '}', ' ']  # all special characters in form of \x

specialCharacterForward = {
    '\\': 'BS',
    '%': 'PC',
    '&': 'AD',
    '#': 'NB',
    '$': 'DL',
    '{': 'LB',
    '}': 'RB',
    '^': 'UT',
    ' ': 'SP',
    '`': 'BQ',
    '~': 'TD',
    "'": 'SQ',
    '"': 'DQ',
    '=': 'EQ',
    '.': 'DT',
    '*': 'ST',
    '@': 'AT',
}
specialCharacterBackward = {specialCharacterForward[key]: key for key in specialCharacterForward}
assert len(set(specialCharacterForward.values())) == len(specialCharacterForward)

environmentList = ['abstract', 'acknowledgments', 'itemize', 'enumerate', 'description', 'list', 'proof', 'quote', 'spacing']
commandList = ['section', 'subsection', 'subsubsection', 'caption', 'subcaption', 'footnote', 'paragraph']
formatList = ['textbf', 'textit', 'emph']
replaceNewcommandList = ['equation', 'array', 'displaymath', 'align', 'multiple', 'gather', 'theorem', 'textcolor'] + environmentList + commandList


def variable_code(count):
    # If count is 123, the code is {math_code}_1_2_3
    digits = list(str(count))
    countStr = "_".join(digits)
    return f'{mathCode}_{countStr}'


def modify_text(text, modifyFunc):
    # modify text without touching the variable codes
    splitText = [s for s in re.split(matchCode, text) if s is not None]
    for i in range(len(splitText)):
        if not re.match(matchCode, splitText[i]):
            splitText[i] = modifyFunc(splitText[i])
    text = "".join(splitText)
    return text


def modify_before(text):
    # mathpix is stupid so sometimes does not add $ $ for \pm
    text = text.replace('\\pm', '$\\pm$')
    # the "." may be treated as end of sentence
    text = text.replace('Eq.', 'equation')
    return text


def modify_after(text):
    # the "_" in the text should be replaced to "\_"
    pattern = r"(?<!\\)_"
    text = re.sub(pattern, r"\\_", text)
    return text


def replace_latex_objects(text, brace=True, commandSimple=True):
    r"""
    Replaces all LaTeX objects in a given text with the format "{math_code}_{digit1}_{digit2}_..._{digit_last}",
    applies a given function to the resulting text (excluding the "{math_code}_{digit1}_{digit2}_..._{digit_last}" parts),
    and returns both the processed text and a list of replaced LaTeX objects.
    Supported LaTeX objects: \[ xxx \], \begin{xxx} \end{xxx}, $$ $$,
    $ $, \( xxx \), \xxx[xxx]{xxx}, \xxx{xxx}, and \xxx.
    Returns the processed text and a list of replaced LaTeX objects.
    """

    # You need to make sure that the input does not contain {math_code}
    # define regular expressions for each LaTeX object
    patternsMulargCommand = [get_pattern_command_full(name, n) for name, n, index in config.mularg_command_list]
    latexObjRegex = [
        r"\$\$(.*?)\$\$",  # $$ $$
        r"\$(.*?)\$",  # $ $
        r"\\\[(.*?)\\\]",  # \[ xxx \]
        r"\\\((.*?)\\\)",  # \( xxx \)
        patternEnv,  # \begin{xxx} \end{xxx}
        patternSet1,
        patternSet2,
    ] + patternsMulargCommand + [patternCommandFull]  # \xxx[xxx]{xxx}
    if brace:
        latexObjRegex.append(patternBrace)
    if commandSimple:
        latexObjRegex.append(patternCommandSimple)  # \xxx

    # iterate through each LaTeX object and replace with "{math_code}_{digit1}_{digit2}_..._{digit_last}"
    count = 0
    replacedObjs = []
    for regexSymbol in latexObjRegex:
        pattern = regex.compile(regexSymbol, regex.DOTALL)
        while pattern.search(text):
            latex_obj = pattern.search(text).group()
            replacedObjs.append(f' {latex_obj} ')
            text = pattern.sub(' ' + variable_code(count) + ' ', text, 1)
            count += 1

    text = modify_text(text, modify_before)
    return text, replacedObjs


def recover_latex_objects(text, replacedObjs, tolerateError=False):
    # recover the latex objects from "replace_latex_objects"
    nobjs = len(replacedObjs)
    matchedIndices = []

    def get_obj(digitStr):
        index = int(''.join(digitStr.split('_')))
        matchedIndices.append(index)
        if index < nobjs:
            return replacedObjs[index]
        else:
            if testEnvironment:
                assert tolerateError
            return '???'

    text = modify_text(text, modify_after)
    pattern = re.compile(matchCodeReplace)
    # count number of mismatch
    total_num = 0
    while True:
        text, numModify = pattern.subn(lambda match: get_obj(match.group(1)), text)
        total_num += numModify
        if numModify == 0:
            break
    nGood = len(set(matchedIndices).intersection(set(range(nobjs))))
    nBad1 = len(matchedIndices) - nGood
    nBad2 = nobjs - nGood
    nBad = max(nBad1, nBad2)
    return text, nBad, nobjs


def remove_tex_comments(text):
    """
    Removes all TeX comments in a given string with the format "% comment text".
    Does not match "\%".
    If "%" is at the beginning of a line then delete this line.
    Returns the processed string.
    """
    text = text.replace(r'\\', f'{mathCode}_BLACKSLASH')
    text = text.replace(r'\%', f'{mathCode}_PERCENT')
    text = re.sub(r"\n\s*%.*?(?=\n)", "", text)
    text = re.sub(r"%.*?(?=\n)", "", text)
    text = text.replace(f'{mathCode}_PERCENT', r'\%')
    text = text.replace(f'{mathCode}_BLACKSLASH', r'\\')

    return text


def split_latex_document(text, beginCode, endCode):
    """
    Splits a document into three parts: the preamble, the body, and the postamble.
    Returns a tuple of the three parts.
    """
    beginDocIndex = text.find(beginCode)
    endDocIndex = text.rfind(endCode)
    if beginDocIndex == -1 or endDocIndex == -1 or endDocIndex <= beginDocIndex:
        assert False, "latex is not complete"
    pre = text[:beginDocIndex + len(beginCode)]
    body = text[beginDocIndex + len(beginCode):endDocIndex]
    post = text[endDocIndex:]
    return body, pre, post


def process_specific_env(latex, function, envName):
    # find all patterns of \begin{env_name}[options] content \end{env_name}
    # then replace `content` by `function(content)`
    pattern = regex.compile(getPatternEnv(envName), regex.DOTALL)

    def process_function(match):
        name = match.group(1)
        assert re.match(envName, name)
        options = match.group(2)
        if options is None:
            options = ''
        content = match.group(3)
        processedContent = function(content)
        return rf'\begin{{{envName}}}{options}{processedContent}\end{{{envName}}}'
    return pattern.sub(process_function, latex)


def process_specific_command(latex, function, commandName):
    # find all patterns of # \{command_name}[options]{content}
    # then replace `content` by `function(content)`
    pattern = regex.compile(get_pattern_command_full(commandName), regex.DOTALL)

    def process_function(match):
        name = match.group(1)
        assert re.match(commandName, name)
        options = match.group(2)
        if options is None:
            options = ''
        content = match.group(4)
        processedContent = function(content)
        return rf'\{commandName}{options}{{{processedContent}}}'
    return pattern.sub(process_function, latex)


def process_mularg_command(latex, function, commandTuple):
    # find all patterns of # \{command_name}[options]{content}
    # then replace `content` by `function(content)`
    commandName, nargs, argsToTranslate = commandTuple
    pattern = regex.compile(get_pattern_command_full(commandName, n=nargs), regex.DOTALL)

    def process_function(match):
        name = match.group(1)
        assert re.match(commandName, name)
        group_index = 2
        contents = []
        for i in range(nargs):
            content = match.group(group_index + 1)
            if i in argsToTranslate:
                content = function(content)
            contents.append(content)
            group_index += 2
        return rf'\{commandName}' + ''.join([rf'{{{content}}}' for content in contents])
    return pattern.sub(process_function, latex)


def process_leading_level_brace(latex, function):
    # leading level means that the {xxx} is not inside other objects, i.e. \command{} or \begin{xxx} \end{xxx}
    # replace `{ content }` by `{ function(content) }`
    text, envs = replace_latex_objects(latex, brace=False)
    bracesContent = []
    count = 0

    def process_function(match):
        nonlocal bracesContent, count
        content = match.group(1)
        # function here is translate_paragraph_latex, which cannot contain replaced environments
        processedContent = function(recover_latex_objects(content, envs)[0])
        result = rf'{{ {processedContent} }}'
        bracesContent.append(result)
        placeholder = f'BRACE{count}BRACE'
        count += 1
        return placeholder

    text = regex.compile(patternBrace, regex.DOTALL).sub(process_function, text)
    latex = recover_latex_objects(text, envs)[0]
    for i in range(count):
        latex = latex.replace(f'BRACE{i}BRACE', bracesContent[i])
    return latex


def split_by_command(latex):
    # split by things like \item
    text, envs = replace_latex_objects(latex, commandSimple=False)

    texts = [(text, '')]

    for pattern, command in [(r'\\item\s+', '\item')]:
        newTexts = []
        for t, sep in texts:
            splitedT = re.split(pattern, t)
            seps = [command for _ in splitedT]
            seps[-1] = sep
            newTexts += list(zip(splitedT, seps))
        texts = newTexts

    seps = [t[1] for t in texts]
    texts = [t[0] for t in texts]
    latexs = [recover_latex_objects(t, envs)[0] for t in texts]
    return latexs, seps


def remove_blank_lines(text):
    pattern = re.compile(r'\n\n+')
    text = pattern.sub('\n', text)
    return text


def insert_macro(text, macro):
    pattern = re.compile(r"\\document(class|style)(\[.*?\])?\{(.*?)\}", re.DOTALL)
    match = pattern.search(text)
    assert match is not None
    start, end = match.span()
    new_text = text[:end] + f"\n{macro}\n" + text[end:]
    return new_text


def is_complete(latexCode):
    # Define regular expressions for \documentclass, \begin{document}, and \end{document}
    documentclassPattern = re.compile(r"\\document(class|style)(\[.*?\])?\{.*?\}", re.DOTALL)
    beginPattern = re.compile(r"\\begin\{document\}")
    endPattern = re.compile(r"\\end\{document\}")

    # Check if \documentclass is present
    if not documentclassPattern.search(latexCode):
        return False

    # Check if \begin{document} is present
    beginMatch = beginPattern.search(latexCode)
    if not beginMatch:
        return False
    beginIndex = beginMatch.start()

    # Check if \end{document} is present
    endMatch = endPattern.search(latexCode)
    if not endMatch:
        return False
    endIndex = endMatch.end()

    # Check if the order is correct
    if beginIndex < documentclassPattern.search(latexCode).end() or endIndex < beginIndex:
        return False

    return True


def get_theorems(text):
    pattern = re.compile(patternTheorem, re.DOTALL)
    matches = re.finditer(pattern, text)
    theorems = [match.group(1) for match in matches]
    return theorems


def get_nonNone(*args):
    result = [arg for arg in args if arg is not None]
    assert len(result) == 1
    return result[0]


def replace_special(text):
    for special in listSpecial:
        # add space around
        text = text.replace(f'\\{special}', f' {mathCode}{specialCharacterForward[special]} ')

    return text


def recover_special(text):
    for special in listSpecial:
        text = text.replace(mathCode + specialCharacterForward[special], f'\\{special}')

    return text


def replace_accent(text):
    def replace_function(match):
        # if it is \"{o}, then special is ", char1 is o, char2 is None
        # if it is \"o, then special is ", char1 is None, char2 is o
        special = match.group(1)
        char1 = match.group(2)
        char2 = match.group(3)
        char = get_nonNone(char1, char2)
        # do not add space around
        return mathCode + specialCharacterForward[special] + f'{char}'

    text = re.compile(patternAccent).sub(replace_function, text)

    return text


def recover_accent(text):
    def replace_function(match):
        special = specialCharacterBackward[match.group(1)]
        char = match.group(2)
        return rf'\{special}{{{char}}}'

    text = re.compile(matchCodeAccent).sub(replace_function, text)

    return text


def combine_split_to_sentences(text):
    # if two lines are separately by only one \n, in latex they are in the same paragraph so we combine them in the same line
    # However we don't combine them if the second line does not start from normal letters (so usually some latex commands)
    n = len(mathCode)
    pattern = re.compile(r'\n(\s*([^\s]+))')

    def process_function(match):
        string = match.group(2)
        if string[0:n] == mathCode:
            return match.group(0)
        else:
            return ' ' + match.group(1)

    return pattern.sub(process_function, text)


def delete_specific_format(latex, formatName):
    pattern = regex.compile(get_pattern_command_full(formatName), regex.DOTALL)
    return pattern.sub(lambda m: ' ' + m.group(4) + ' ', latex)


def replace_newcommand(newcommand, latex):
    commandName, nArguments, content = newcommand
    pattern = regex.compile(get_pattern_command_full(commandName, nArguments), regex.DOTALL)

    def replace_function(match):
        thisContent = content
        name = match.group(1)
        assert re.match(commandName, name)
        for i in range(nArguments):
            text = match.group(3 + i * 2)
            thisContent = thisContent.replace(f'#{i+1}', f' {text} ')
        return thisContent

    return pattern.sub(replace_function, latex)


def process_newcommands(latex):
    pattern = regex.compile(patternNewcommand, regex.DOTALL)
    count = 0
    fullNewcommands = []
    matchesAll = list(regex.finditer(pattern, latex))
    for match in matchesAll:
        needReplace = False
        contentAll = match.group(0)
        for special in replaceNewcommandList:
            if special in contentAll:
                needReplace = True
        if not needReplace:
            continue
        name1 = match.group(1)
        name2 = match.group(2)
        name = get_nonNone(name1, name2)
        nArguments = match.group(3)
        if nArguments is None:
            nArguments = 0
        else:
            nArguments = int(nArguments)
        content = match.group(5)
        latex = latex.replace(match.group(), f'{mathCode}_REPLACE{count}_NEWCOMMAND')
        fullNewcommands.append(match.group(0))
        latex = replace_newcommand((name, nArguments, content), latex)
        count += 1
    for i in range(count):
        latex = latex.replace(f'{mathCode}_REPLACE{i}_NEWCOMMAND', fullNewcommands[i])
    return latex


def remove_bibnote(latex):
    pattern = regex.compile(get_pattern_command_full('bibinfo', 2), regex.DOTALL)

    def replace_function(match):
        assert match.group(1) == 'bibinfo'
        if match.group(3) == 'note':
            return ''
        else:
            return match.group(0)
    return pattern.sub(replace_function, latex)
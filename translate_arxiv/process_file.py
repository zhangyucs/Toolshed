import os
import re
from process_latex import remove_tex_comments
from encoding import get_file_encoding


def merge_complete(tex):
    '''
    for replace all \input commands by the file content
    '''
    path = f'{tex}.tex'
    dirname = os.path.dirname(path)
    encoding = get_file_encoding(path)
    content = open(path, encoding=encoding).read()
    content = remove_tex_comments(content)
    patternInput = re.compile(r'\\input{(.*?)}')
    while True:
        result = patternInput.search(content)
        if result is None:
            break
        begin, end = result.span()
        match = result.group(1)
        filename = os.path.join(dirname, match)
        if os.path.exists(f'{filename}.tex'):
            filename = f'{filename}.tex'
        print('merging', filename)
        assert os.path.exists(filename)
        encoding = get_file_encoding(filename)
        newContent = open(filename, encoding=encoding).read()
        newContent = remove_tex_comments(newContent)
        content = content[:begin] + newContent + content[end:]
    print(content, file=open(path, "w", encoding='utf-8'))


def add_bbl(tex):
    '''
    for replace \bibliography commands by the corresponding bbl file
    '''
    pathTex = f'{tex}.tex'
    pathBbl = f'{tex}.bbl'
    encoding = get_file_encoding(pathTex)
    content = open(pathTex, encoding=encoding).read()
    encoding = get_file_encoding(pathBbl)
    bbl = open(pathBbl, encoding=encoding).read()
    patterns = [r'\\bibliography\{(.*?)\}', r'\\thebibliography\{(.*?)\}']
    for pattern in patterns:
        patternInput = re.compile(pattern, re.DOTALL)
        while True:
            result = patternInput.search(content)
            if result is None:
                break
            begin, end = result.span()
            content = content[:begin] + bbl + content[end:]
        print(content, file=open(pathTex, "w", encoding='utf-8'))

import process_latex
import process_text
import cache
from config import config
from process_latex import environmentList, commandList, formatList
from process_text import charLimit
from encoding import get_file_encoding
import time
import re
import tqdm.auto
import concurrent.futures
import mtranslate as translator


defaultBegin = r'''
\documentclass[UTF8]{article}
\usepackage{xeCJK}
\usepackage{amsmath,amssymb}
\begin{document}
'''
defaultEnd = r'''
\end{document}
'''


class TextTranslator:
    def __init__(self, engine, languageTo, languageFrom):
        self.engine = engine
        self.translator = translator
        self.languageTo = languageTo
        self.languageFrom = languageFrom
        self.numberOfCalls = 0
        self.totChar = 0

    def try_translate(self, text):
        return self.translator.translate(text, self.languageTo, self.languageFrom)

    def translate(self, text):
        if not re.match(re.compile(r'.*[a-zA-Z].*', re.DOTALL), text):
            # no meaningful word inside
            return text
        while True:
            try:
                result = self.try_translate(text)
                break
            except BaseException as e:
                if hasattr(self.translator, "is_error_request_frequency") and self.translator.is_error_request_frequency(e):
                    time.sleep(0.5)
                else:
                    raise e
        self.numberOfCalls += 1
        self.totChar += len(text)
        return result


class LatexTranslator:
    def __init__(self, translator: TextTranslator, debug=False, threads=0):
        self.translator = translator
        self.debug = debug
        if self.debug:
            self.fOld = open("text_old", "w", encoding='utf-8')
            self.fNew = open("text_new", "w", encoding='utf-8')
            self.fObj = open("objs", "w", encoding='utf-8')
        if threads == 0:
            self.threads = None
        else:
            self.threads = threads

    def close(self):
        if self.debug:
            self.fOld.close()
            self.fNew.close()
            self.fObj.close()

    def translate_paragraph_text(self, text):
        '''
        Translators would have a word limit for each translation
        So here we split translation by '\n' if it's going to exceed limit
        '''
        lines = text.split('\n')
        parts = []
        part = ''
        for line in lines:
            if len(line) >= charLimit:
                assert False, "one line is too long"
            if len(part) + len(line) < charLimit - 10:
                part = part + '\n' + line
            else:
                parts.append(part)
                part = line
        parts.append(part)
        partsTranslated = []
        for part in parts:
            partsTranslated.append(self.translator.translate(part))
        textTranslated = '\n'.join(partsTranslated)
        return textTranslated.replace("\u200b", "")

    def _translate_text_in_paragraph_latex(self, latexOriginalParagraph):
        '''
        Translate a latex paragraph, which means that it could contain latex objects
        '''

        # remove format about textbf, emph and textit
        for formatName in formatList:
            latexOriginalParagraph = process_latex.delete_specific_format(latexOriginalParagraph, formatName)

        textOriginalParagraph, objs = process_latex.replace_latex_objects(latexOriginalParagraph)
        # Since \n is equivalent to space in latex, we change \n back to space
        # otherwise the translators view them as separate sentences
        textOriginalParagraph = process_latex.combine_split_to_sentences(textOriginalParagraph)
        textOriginalParagraph = process_text.split_too_long_paragraphs(textOriginalParagraph)
        if not self.complete:
            textOriginalParagraph = process_text.split_titles(textOriginalParagraph)
        # Remove additional space
        textOriginalParagraph = re.sub(r'  +', ' ', textOriginalParagraph)
        if self.debug:
            print(f'\n\nParagraph {self.num}\n\n', file=self.fOld)
            print(textOriginalParagraph, file=self.fOld)
        textTranslatedParagraph = self.translate_paragraph_text(textOriginalParagraph)
        if self.debug:
            print(f'\n\nParagraph {self.num}\n\n', file=self.fNew)
            print(textTranslatedParagraph, file=self.fNew)
            print(f'\n\nParagraph {self.num}\n\n', file=self.fObj)
            for i, obj in enumerate(objs):
                print(f'obj {i}', file=self.fObj)
                print(obj, file=self.fObj)
        latexTranslatedParagraph, nbad, ntotal = process_latex.recover_latex_objects(textTranslatedParagraph, objs, tolerateError=True)
        self.nbad += nbad
        self.ntotal += ntotal
        return latexTranslatedParagraph

    def translate_text_in_paragraph_latex(self, paragraph):
        splitedParagraphs, seps = process_latex.split_by_command(paragraph)
        result = ''
        for split, sep in zip(splitedParagraphs, seps):
            result += self._translate_text_in_paragraph_latex(split) + ' ' + sep + ' '
        return result

    def translate_latex_all_objects(self, latex):
        '''
        Terminology:
        env: '\\begin{xxx} \\end{xxx}'
        command: '\\command[options]{text}
        object: env or command
        '''
        translateFunction = self.translate_text_in_paragraph_latex_and_leading_brace
        for envName in environmentList + self.theorems:
            latex = process_latex.process_specific_env(latex, translateFunction, envName)
            latex = process_latex.process_specific_env(latex, translateFunction, envName + r'\*')
        for commandName in commandList:
            latex = process_latex.process_specific_command(latex, translateFunction, commandName)
            latex = process_latex.process_specific_command(latex, translateFunction, commandName + r'\*')
        for commandGroup in config.mularg_command_list:
            latex = process_latex.process_mularg_command(latex, translateFunction, commandGroup)
        return latex

    def translate_text_in_paragraph_latex_and_leading_brace(self, latexOriginalParagraph):
        # it acts recursively, i.e. it also translates braces inside braces
        latexTranslatedParagraph = self.translate_text_in_paragraph_latex(latexOriginalParagraph)
        latexTranslatedParagraph = process_latex.process_leading_level_brace(latexTranslatedParagraph, self.translate_text_in_paragraph_latex_and_leading_brace)
        return latexTranslatedParagraph

    def translate_paragraph_latex(self, latexOriginalParagraph):
        latexTranslatedParagraph = self.translate_text_in_paragraph_latex_and_leading_brace(latexOriginalParagraph)
        latexTranslatedParagraph = self.translate_latex_all_objects(latexTranslatedParagraph)
        return latexTranslatedParagraph

    def split_latex_to_paragraphs(self, latex):
        '''
        1. convert latex to text and objects
        2. split text
        3. convert text back to objects
        '''
        text, objs = process_latex.replace_latex_objects(latex)
        paragraphsText = re.split(r'\n\n+', text)
        paragraphsLatex = [process_latex.recover_latex_objects(paragraphText, objs)[0] for paragraphText in paragraphsText]
        return paragraphsLatex

    def worker(self, latexOriginalParagraph):
        try:
            if self.addCache:
                hashKeyParagraph = cache.deterministic_hash(latexOriginalParagraph)
                latexTranslatedParagraph = cache.load_paragraph(self.hashKey, hashKeyParagraph)
                if latexTranslatedParagraph is None:
                    latexTranslatedParagraph = self.translate_paragraph_latex(latexOriginalParagraph)
                    cache.write_paragraph(self.hashKey, hashKeyParagraph, latexTranslatedParagraph)
            else:
                latexTranslatedParagraph = self.translate_paragraph_latex(latexOriginalParagraph)
            self.num += 1
            return latexTranslatedParagraph
        except BaseException as e:
            print('Error found in Parapragh', self.num)
            print('Content')
            print(latexOriginalParagraph)
            raise e

    def translate_full_latex(self, latexOriginal, makeComplete=True, noCache=False):
        self.addCache = (not noCache)
        if self.addCache:
            cache.remove_extra()
            # self.hashKey = cache.deterministic_hash((latexOriginal, __version__, self.translator.engine, self.translator.languageFrom, self.translator.languageTo, config.mularg_command_list))
            self.hashKey = cache.deterministic_hash((latexOriginal, self.translator.engine, self.translator.languageFrom, self.translator.languageTo, config.mularg_command_list))
            if cache.is_cached(self.hashKey):
                print('Cache is found')
            cache.create_cache(self.hashKey)

        self.nbad = 0
        self.ntotal = 0

        latexOriginal = process_latex.remove_tex_comments(latexOriginal)
        latexOriginal = latexOriginal.replace(r'\mathbf', r'\boldsymbol')
        # \bibinfo {note} is not working in xelatex
        latexOriginal = process_latex.remove_bibnote(latexOriginal)
        latexOriginal = process_latex.process_newcommands(latexOriginal)

        latexOriginal = process_latex.replace_accent(latexOriginal)
        latexOriginal = process_latex.replace_special(latexOriginal)

        self.complete = process_latex.is_complete(latexOriginal)
        self.theorems = process_latex.get_theorems(latexOriginal)
        if self.complete:
            print('It is a full latex document')
            latexOriginal, texBegin, texEnd = process_latex.split_latex_document(latexOriginal, r'\begin{document}', r'\end{document}')
            texBegin = process_latex.remove_blank_lines(texBegin)
            texBegin = process_latex.insert_macro(texBegin, '\\usepackage{xeCJK}\n\\usepackage{amsmath}')
        else:
            print('It is not a full latex document')
            latexOriginal = process_text.connect_paragraphs(latexOriginal)
            if makeComplete:
                texBegin = defaultBegin
                texEnd = defaultEnd
            else:
                texBegin = ''
                texEnd = ''

        latexOriginalParagraphs = self.split_latex_to_paragraphs(latexOriginal)
        latexTranslatedParagraphs = []
        self.num = 0
        # tqdm with concurrent.futures.ThreadPoolExecutor()
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            latexTranslatedParagraphs = list(tqdm.auto.tqdm(executor.map(self.worker, latexOriginalParagraphs), total=len(latexOriginalParagraphs)))

        latexTranslated = '\n\n'.join(latexTranslatedParagraphs)

        latexTranslated = texBegin + '\n' + latexTranslated + '\n' + texEnd

        # Title is probably outside the body part
        self.num = 'title'
        latexTranslated = process_latex.process_specific_command(latexTranslated, self.translate_text_in_paragraph_latex, 'title')

        latexTranslated = latexTranslated.replace('%', '\\%')
        latexTranslated = process_latex.recover_special(latexTranslated)
        latexTranslated = process_latex.recover_accent(latexTranslated)

        self.close()

        print(self.ntotal - self.nbad, '/',  self.ntotal, 'latex object are correctly translated')

        return latexTranslated


def translate_single_tex_file(input_path, outputPath, engine, lFrom, lTo, debug, nocache, threads):
    textTranslator = TextTranslator(engine, lTo, lFrom)
    latexTranslator = LatexTranslator(textTranslator, debug, threads)

    inputEncoding = get_file_encoding(input_path)
    textOriginal = open(input_path, encoding=inputEncoding).read()
    text_final = latexTranslator.translate_full_latex(textOriginal, noCache=nocache)
    with open(outputPath, "w", encoding='utf-8') as file:
        print(text_final, file=file)
    print('Number of translation called:', textTranslator.numberOfCalls)
    print('Total characters translated:', textTranslator.totChar)
    print('saved to', outputPath)
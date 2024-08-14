import requests
import utils
import process_latex
import process_file
from translate import translate_single_tex_file
from encoding import get_file_encoding
import os
import sys
import shutil
import gzip
import zipfile
import tarfile
import tempfile
import urllib.request
from cache import cache_dir
import argparse


def download_source(number, path):
    url = f'https://arxiv.org/e-print/{number}'
    print('trying to download from', url)
    urllib.request.urlretrieve(url, path)


def download_arxiv_pdf(arxivId, savePath):
    url = f'https://arxiv.org/pdf/{arxivId}.pdf'
    response = requests.get(url)
    if response.status_code == 200:
        with open(savePath, 'wb') as file:
            file.write(response.content)
        print(f"File downloaded successfully and saved as {savePath}")
    else:
        print(f"Failed to download file from {url}, status code: {response.status_code}")


def download_source_with_cache(number, path):
    cacheDir = os.path.join(cache_dir(), 'cache_arxiv')
    os.makedirs(cacheDir, exist_ok=True)
    cachePath = os.path.join(cacheDir, 'last_downloaded_source')
    cacheNumberPath = os.path.join(cacheDir, 'last_arxiv_number')
    if os.path.exists(cachePath) and os.path.exists(cacheNumberPath):
        lastNumber = open(cacheNumberPath).read()
        if lastNumber == number:
            shutil.copyfile(cachePath, path)
            return
    download_source(number, path)
    shutil.copyfile(path, cachePath)
    open(cacheNumberPath, 'w').write(number)


def is_pdf(fileName):
    return open(fileName, 'rb').readline()[0:4] == b'%PDF'


def loop_files(dir):
    allFiles = []
    for root, dirs, files in os.walk(dir):
        for file in files:
            allFiles.append(os.path.join(root, file))
    return allFiles


def zipdir(dir, outputPath):
    zipFile = zipfile.ZipFile(outputPath, 'w', zipfile.ZIP_DEFLATED)
    for file in loop_files(dir):
        relPath = os.path.relpath(file, dir)
        zipFile.write(file, arcname=relPath)


def translate_dir(dir, options):
    files = loop_files(dir)
    texs = [f[0:-4] for f in files if f[-4:] == '.tex']
    bibs = [f[0:-4] for f in files if f[-4:] == '.bib']
    bbls = [f[0:-4] for f in files if f[-4:] == '.bbl']
    noBib = len(bibs) == 0
    print('main tex files found:')
    completeTexs = []
    for tex in texs:
        path = f'{tex}.tex'
        inputEncoding = get_file_encoding(path)
        content = open(path, encoding=inputEncoding).read()
        content = process_latex.remove_tex_comments(content)
        complete = process_latex.is_complete(content)
        if complete:
            print(path)
            process_file.merge_complete(tex)
            if noBib and (tex in bbls):
                process_file.add_bbl(tex)
            completeTexs.append(tex)
    if len(completeTexs) == 0:
        return False
    for basename in texs:
        if basename in completeTexs:
            continue
        os.remove(f'{basename}.tex')
    for basename in bbls:
        os.remove(f'{basename}.bbl')
    if options.notranslate:
        return True
    for filename in completeTexs:
        print(f'Processing {filename}')
        filePath = f'{filename}.tex'
        translate_single_tex_file(filePath, filePath, options.engine, options.l_from, options.l_to, options.debug, options.nocache, options.threads)
    return True


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("number", nargs='?', type=str, help='arxiv number')
    parser.add_argument("-o", type=str, help='output path')
    parser.add_argument("--from_dir", action='store_true')
    parser.add_argument("--notranslate", action='store_true') 
    utils.add_arguments(parser)
    options = parser.parse_args(args)
    utils.process_options(options)

    if options.number is None:
        parser.print_help()
        sys.exit()

    number = options.number
    print('arxiv number:', number)
    print()
    downloadPath = number.replace('/', '-')
    if options.o is None:
        outputPath = f'{downloadPath}.zip'
    else:
        outputPath = options.o

    success = True
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tempDir:
        print('temporary directory', tempDir)
        if options.from_dir:
            shutil.copytree(number, tempDir, dirs_exist_ok=True)
        os.chdir(tempDir)
        try:
            if not options.from_dir:
                try:
                    download_source_with_cache(number, downloadPath)
                    savePath = os.path.join(cwd, number+'.pdf')
                    download_arxiv_pdf(number, savePath)
                except BaseException:
                    print('Cannot download source, maybe network issue or wrong link')
                    os.chdir(cwd)
                    return False
                if is_pdf(downloadPath):
                    success = False
                else:
                    content = gzip.decompress(open(downloadPath, "rb").read())
                    with open(downloadPath, "wb") as f:
                        f.write(content)
                    try:
                        with tarfile.open(downloadPath, mode='r') as f:
                            f.extractall()
                        os.remove(downloadPath)
                    except tarfile.ReadError:
                        print('This is a pure text file')
                        shutil.move(downloadPath, 'main.tex')
                    success = translate_dir('.', options)
            else:
                success = translate_dir('.', options)
            os.chdir(cwd)
            if success:
                zipdir(tempDir, outputPath)
        except BaseException as e:
            os.chdir(cwd)
            raise e

    if success:
        print('zip file is saved to', outputPath)
        return True
    else:
        print('Source code is not available for arxiv', number)
        return False


if __name__ == '__main__':
    main()

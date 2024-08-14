import argparse
import os
import shutil
import subprocess
import zipfile
import utils


def find_and_copy_pdf(directory):
    files = os.listdir(directory)
    for file in files:
        if file.endswith(".tex"):
            texFile = os.path.splitext(file)[0]
            pdfFile = texFile + ".pdf"
            pdfPath = os.path.join(directory, pdfFile)
            if os.path.exists(pdfPath):
                outputFile = directory + "_zh.pdf"
                outputPath = os.path.join(os.getcwd(), outputFile)
                try:
                    shutil.copy(pdfPath, outputPath)
                    print(f"Copied and renamed '{pdfPath}' to '{outputPath}'.")
                except Exception as e:
                    print(f"An error occurred while copying the file: {e}")
            else:
                print(f"PDF file '{pdfPath}' does not exist in the directory.")
            break
    else:
        print("No .tex file found in the directory.")


def compile_latex_to_pdf(directory):
    os.chdir(directory)
    mainTex = next((file for file in os.listdir() if file.endswith('.tex')), None)
    if not mainTex:
        print("Error: .tex file not found")
        return
    baseName = os.path.splitext(mainTex)[0]
    commands = [
        ["xelatex", "-interaction=nonstopmode", baseName],
        ["bibtex", baseName],
        ["xelatex", "-interaction=nonstopmode", baseName],
        ["xelatex", "-interaction=nonstopmode", baseName]
    ]
    for command in commands:
        subprocess.run(command, check=True)


def unzip_to_folder(zipPath):
    zipName = zipPath + ".zip"
    folderName = os.path.splitext(os.path.basename(zipName))[0]
    outputPath = os.path.join(os.getcwd(), folderName)
    os.makedirs(outputPath, exist_ok=True)
    with zipfile.ZipFile(zipName, 'r') as zipRef:
        zipRef.extractall(outputPath)
    print(f"The decompression is complete and the file has been extracted to: {outputPath}")


def main(args=None):

    parser = argparse.ArgumentParser()
    parser.add_argument("number", nargs='?', type=str, help='arxiv number')
    utils.add_arguments(parser)
    options = parser.parse_args(args)
    utils.process_options(options)

    latexDirectory = options.number

    if not os.path.exists(latexDirectory):
        unzip_to_folder(latexDirectory)
    else:
        print(f"{latexDirectory} already exists")

    cwd = os.getcwd()
    try:
        compile_latex_to_pdf(latexDirectory)
    except:
        print("If the generated PDF file has a format error, please try again")
    finally:
        os.chdir(cwd)
        find_and_copy_pdf(latexDirectory)


if __name__ == '__main__':
    main()
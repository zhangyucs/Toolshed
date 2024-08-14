import os
import time
import hashlib
import shutil


def cache_dir():
    cachePath = os.path.join(os.getcwd(), 'arxiv_cache')
    if not os.path.exists(cachePath):
        os.mkdir(cachePath)
    return cachePath

cacheDir = os.path.join(cache_dir(), 'cache')
os.makedirs(cacheDir, exist_ok=True)
timeFilename = 'update_time'
maxCache = 5


def deterministic_hash(obj):
    hashObject = hashlib.sha256()
    hashObject.update(str(obj).encode())
    return hashObject.hexdigest()[0:20]


def get_dirs():
    dirs = [os.path.join(cacheDir, dir) for dir in os.listdir(cacheDir) if os.path.isdir(os.path.join(cacheDir, dir))]
    return dirs


def get_time(dir):
    try:
        timeFile = os.path.join(dir, timeFilename)
        t = float(open(timeFile, encoding='utf-8').read())
        return t
    except FileNotFoundError:
        # handle the error as needed, for now we'll just return a default value
        return float('inf')  # This ensures that this directory will be the first to be removed if required


def write_time(dir):
    timeFile = os.path.join(dir, timeFilename)
    t = time.time()
    print(t, file=open(timeFile, "w", encoding='utf-8'), end='')


def argmin(iterable):
    return min(enumerate(iterable), key=lambda x: x[1])[0]


def remove_extra():
    dirs = get_dirs()
    for dir in dirs:
        if not os.path.isdir(dir):  # This line might be redundant now, as get_dirs() ensures only directories are returned
            os.remove(dir)
        try:
            get_time(dir)
        except BaseException:
            shutil.rmtree(dir)
    while True:
        dirs = get_dirs()
        if len(dirs) <= maxCache:
            break
        times = [get_time(dir) for dir in dirs]
        arg = argmin(times)
        shutil.rmtree(dirs[arg])


def is_cached(hashKey):
    dir = os.path.join(cacheDir, hashKey)
    return os.path.exists(dir)


def create_cache(hashKey):
    dir = os.path.join(cacheDir, hashKey)
    os.makedirs(dir, exist_ok=True)
    write_time(dir)


def load_paragraph(hashKey, hashKeyParagraph):
    filename = os.path.join(cacheDir, hashKey, hashKeyParagraph)
    if os.path.exists(filename):
        return open(filename, encoding='utf-8').read()
    else:
        return None


def write_paragraph(hashKey, hashKeyParagraph, paragraph):
    filename = os.path.join(cacheDir, hashKey, hashKeyParagraph)
    print(paragraph, file=open(filename, "w", encoding='utf-8'), end='')
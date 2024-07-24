import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid


def read_local_m3u8(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    ts_urls = [line.strip() for line in lines if line.strip().endswith('.ts')]
    return ts_urls

def merge_ts_files(ffmpeg_path, m3u8_path, output_mp4):
    ts_files = read_local_m3u8(m3u8_path)
    temp_filelist = f"filelist_{uuid.uuid4().hex}.txt"
    sp1, sp2 = os.path.split(m3u8_path)
    with open(temp_filelist, 'w') as file:
        for ts in ts_files:
            file.write(f"file '{os.path.join(sp1, ts)}'\n")
    command = [ffmpeg_path, '-f', 'concat', '-safe', '0', '-i', temp_filelist, '-c', 'copy', output_mp4]
    subprocess.run(command)
    os.remove(temp_filelist)

def process_m3u8_file(ffmpeg_path, m3u8_path, output_dir):
    s1, s2 = os.path.split(m3u8_path)
    output_mp4 = os.path.join(output_dir, os.path.basename(s1).replace('.m3u8', '.mp4'))
    merge_ts_files(ffmpeg_path, m3u8_path, output_mp4)

def main(ffmpeg_path, m3u8_paths, output_dir, max_workers):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_m3u8_file, ffmpeg_path, m3u8_path, output_dir) for m3u8_path in m3u8_paths]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error occurred: {e}")


if __name__ == '__main__':
    ffmpeg_path = './ffmpeg.exe'
    m3u8_paths = [
        '1.m3u8/index.m3u8', '2.m3u8/index.m3u8', '3.m3u8/index.m3u8', 
        '4.m3u8/index.m3u8', '5.m3u8/index.m3u8', '6.m3u8/index.m3u8', 
        '7.m3u8/index.m3u8', '8.m3u8/index.m3u8', '9.m3u8/index.m3u8', 
        '10.m3u8/index.m3u8', '11.m3u8/index.m3u8', '12.m3u8/index.m3u8'
    ]
    output_dir = 'output'
    max_workers = 3

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    main(ffmpeg_path, m3u8_paths, output_dir, max_workers)

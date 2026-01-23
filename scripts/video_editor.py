import subprocess
import os

def run_ffmpeg(options: dict):
    option_str = ' '.join([f'{str(key)} {str(value)}' for key, value in options.items()])
    command = 'ffmpeg ' + option_str
    out = subprocess.run(command, capture_output=True, shell=True)
    return out

def reencode_video():
    pass

def crop_trim(file_in: str, file_out: str, x: int, y: int, width: int, height: int, t_start: int, t_end: int):
    '''
    Docstring for crop
    
    :param file_in: input filepath
    :type file_in: str
    :param file_out: output filepath
    :type file_out: str
    :param x: pixels from left edge
    :type x: int
    :param y: pixels
    :type y: int
    :param width: pixels
    :type width: int
    :param height: pixels
    :type height: int
    :param t_start: Seconds
    :type t_start: int 
    :param t_end: Seconds
    :type t_end: int
    '''

    if os.path.exists(file_in) == False:
        raise FileNotFoundError(f"Input file not found: {file_in}")
    if os.path.exists(file_out):
        os.remove(file_out)

    options = {
        "-i"     : file_in,
        "-ss"    : t_start,
        "-t"     : t_end-t_start,
        "-vf"    : f"crop={width}:{height}:{x}:{y}",
        ""       : file_out
    }
    result = run_ffmpeg(options)
    return result.returncode

if __name__ == "__main__":
    f_in = "C:\\Users\\nullm\\OneDrive\\Desktop\\boxcar\\test.mpeg"
    f_out = "C:\\Users\\nullm\\OneDrive\\Desktop\\boxcar\\test_out.mpeg"
    crop_trim(f_in, f_out, 500, 500, 200, 200, 2, 5)
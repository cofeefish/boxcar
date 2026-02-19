import subprocess
import os

def run_ffmpeg(options: dict):
    option_str = ' '.join([f'{str(key)} {str(value)}' for key, value in options.items()])
    command = 'ffmpeg ' + option_str
    out = subprocess.run(command, capture_output=True, shell=True)
    print("FFMPEG COMMAND:")
    print(command)
    print("FFMPEG STDOUT:")
    print(out.stdout.decode())
    print("FFMPEG STDERR:")
    print(out.stderr.decode())
    return out

def reencode_video():
    pass

def crop_trim(file_in: str, file_out: str, x: int|None, y: int|None, width: int|None, height: int|None,
               t_start: float|None, t_end: float|None, gain: float = 1.0) -> int:
    '''
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
    file_path, file_ext = os.path.splitext(file_in)
    temp_output = False
    if file_in == file_out:
        file_out = file_path + "_temp_output" + file_ext
        temp_output = True
    file_in = os.path.normpath(file_in)
    file_out = os.path.normpath(file_out)
    if os.path.exists(file_out):
        os.remove(file_out)
    file_in  = '"' + file_in + '"'
    file_out = '"' + file_out + '"'

    crop = True if (all([x!=None for x in [x, y, width, height]])) else False
    trim = True if (t_start!=None and t_end != None) else False

    options = {}
    if ( (not crop) and (not trim) ):
        #no crop, no trim
        options = {
            "-i"     : file_in,
            "-af"    : f"volume={gain}dB",
            ""       : file_out
        }
    elif ( (crop) and (not trim) ):
          #crop, no trim
        options = {
            "-i"     : file_in,
            "-vf"    : f"crop={width}:{height}:{x}:{y}",
            "-af"    : f"volume={gain}dB",
            ""       : file_out
        }
    elif ( (not crop) and (trim) ):
        #no crop, trim
        options = {
            "-i"     : file_in,
            "-ss"    : t_start,
            "-t"     : t_end-t_start, # type: ignore
            "-af"    : f"volume={gain}dB",
            ""       : file_out
        }
    elif ( crop and trim ):
        #crop + trim
        options = {
            "-i"     : file_in,
            "-ss"    : t_start,
            "-t"     : t_end-t_start, # type: ignore
            "-vf"    : f"crop={width}:{height}:{x}:{y}",
            "-af"    : f"volume={gain}dB",
            ""       : file_out
        }
    result = run_ffmpeg(options)

    if result.returncode == 0:
        if temp_output:
            os.replace(file_out.strip('"'), file_in.strip('"'))
    else:
        print("FFMPEG ERROR:")
        print(result.stderr.decode())
    return result.returncode

if __name__ == "__main__":
    f_in = "C:\\Users\\nullm\\OneDrive\\Desktop\\boxcar\\test.mpeg"
    f_out = "C:\\Users\\nullm\\OneDrive\\Desktop\\boxcar\\test_out.mpeg"
    crop_trim(f_in, f_out, 500, 500, 200, 200, 2, 5)
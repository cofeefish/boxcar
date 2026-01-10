import os, time, subprocess, database
import  logging
from flask import url_for
from PIL import Image
import cv2

dataset_dir = database.dataset_dir
source_dir = database.source_dir
temp_dir = database.temp_dir
post_table_path = database.post_table_path


image_extensions = ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'svg', 'gif']
video_extensions = ['mp4', 'webm', 'avi', 'flv', 'mov', 'wmv', 'mkv', 'm4v']

def is_float(string:str) -> bool:
    try:
        float(string)
        return True
    except ValueError:
        return False

def initialize():
    #verify dataset directory exists
    database.initialize_database(reset=False)
    #verify ffmpeg is installed
    out = subprocess.call('ffmpeg -version', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if out != 0:
        raise RuntimeError("ffmpeg not found, please install ffmpeg and ensure it is in your system PATH")

dimensions = database.get_setting("thumbnail_width"), database.get_setting("thumbnail_height")
def make_thumbnaill(path: str, size:tuple = dimensions , to_link=False, name="", final_ext='png') -> str:
    #check if path is valid first to save time
    if not os.path.isfile(path):
        #print(f'path: {path} while trying to creatye thumbnail')
        return ""
    t=database.quicktimer("\n\nTHUMBNAIL: import and setup")
    base, ext = os.path.splitext(path)
    ext = ext.lower().strip('.')
    if name == "":
        name = os.path.basename(base)
    if database.keep_thumbnails == True:
        thumbnail_path = f'{dataset_dir}/thumbnails/{name}.{final_ext}'
    else:
        thumbnail_path = f'{source_dir}/static/temp/{name}_thumbnail.{final_ext}'
    #t.finish()
    t=database.quicktimer('from video')
    if ext.lower() in video_extensions:
        vidcap = cv2.VideoCapture(path)
        success, image = vidcap.read()
        if success: 
            cv2.imwrite(thumbnail_path, image)
            vidcap.release()
            path = thumbnail_path
        else:
            vidcap.release()
            print(f'error, could not open video file {path} to create thumbnail')
            return ""
        base, ext = os.path.splitext(path)
        ext = ext.lower().strip('.')
    #t.finish()
    t=database.quicktimer("resize")
    if not (ext in image_extensions):
        print(f'error, could not open file {path} to create thumbnail')
        print(ext)
        return ""
    with Image.open(path) as img:
        img.thumbnail(size)
        img.save(thumbnail_path)
    #t.finish()

    if to_link:
        thumbnail_path = url_for('media', filename=thumbnail_path)
    return thumbnail_path

#
def get_similarity(str1:str, str2:str, match_case=True) -> int:
    '''
    get edit (Damerau-Levenshtein) distance between two strings
    strings are stripped
    works by creating a table, the x-axis is str1, the y-axis is str 2. a points value is the cost
    
    :param str1: Description
    :type str1: str
    :param str2: Description
    :type str2: str
    :return: Description
    :rtype: int
    '''
    if not match_case:
        str1=str1.lower()
        str2=str2.lower()
    if str1 == str2: return 0
    str1=str1.strip()
    str2=str2.strip()
    if len(str1) < len(str2):
        str1, str2 = str2, str1

    row_size = len(str2)+1
    col_size = len(str1)+1
    previous_row = list(range(row_size))
    current_row = [0 for x in range(row_size)]

    for row_index in range(1, col_size):
        current_row[0] = row_index
        for col_index in range(1, row_size):
            cost = 0 if str1[row_index-1] == str2[col_index-1] else 1
            
            deletion_cost     = previous_row[col_index] + 1
            insertion_cost    = previous_row[col_index-1] + 1
            substitution_cost = previous_row[col_index-1] + cost
            current_row[col_index] = min(deletion_cost, insertion_cost, substitution_cost)
            # Check for transposition
            letters_transposed = True if (
                (str1[row_index-1] == str2[col_index-2])
                and 
                (str1[row_index-2] == str2[col_index-1])
                ) else False
            if ((row_index > 1) and (col_index > 1) and (letters_transposed)):
                current_row[col_index] = min(
                    current_row[col_index],
                    previous_row[col_index-2] + 1 # transposition
                )
        # Swap rows
        previous_row, current_row = current_row, [0 for x in range(row_size)]
        
    return previous_row[-1]

def rank_similarity(comparison: str, choices: list[str], soft_max=False)->list[list]:
    '''
    orders choices by their similarity to the comparison \n

    
    :param base_str: Description
    :type base_str: str
    :param choices: Description
    :type choices: list
    :return: ordered list of choices: [choice, similarity]
    :rtype: list[list]
    '''
    import math

    ordered = []
    for choice in choices:
        similarity = get_similarity(comparison, choice)
        ordered.append([choice, similarity])

    if soft_max:
        total=sum([math.exp(y) for x, y in ordered])
        for i, pair in enumerate(ordered):
            value=(math.exp(pair[1]))/total
            ordered[i] = [pair[0], value]

    ordered.sort(key=lambda x: x[-1], reverse=False)
    return ordered

#file stuff
def file_append(path: str, new: str):
    with open(path, 'a') as file:
        file.write(new)

import hashlib
def get_media_attributes(path: str) -> dict:
    path = path.strip("'")
    file_ext = path.split('.')[-1].lower()
    attributes = {
        "filepath"    : path,
        "file_ext"     : file_ext,
        "file_size"    : os.path.getsize(path),
        "md5"          : "",
        "media_height" : 0,
        "media_width"  : 0,
        "duration"     : 0,
        "length"       : 0,
        "framerate"    : 0,
        "thumbnail"    : ""
        }
    
    if os.path.isfile(path) == False:
        print(f'error, file not found: {path}')
        return attributes

    hasher = hashlib.md5()

    if file_ext in image_extensions:
        with Image.open(path) as img:
            width, height = img.size
            with open(path, 'rb') as afile:
                buf = afile.read()
                hasher.update(buf)
            attributes["md5"]          = hasher.hexdigest()
            attributes["media_height"] = height
            attributes["media_width"]  = width
            attributes["duration"]     = img.info.get('duration', 0)
            attributes["length"]       = img.n_frames if hasattr(img, "n_frames") else 1  # type: ignore
            attributes["framerate"]    = attributes["length"] / attributes["duration"] if attributes["duration"] > 0 else 0.0
            thumbnail_path = make_thumbnaill(path)
            attributes["thumbnail"]    = thumbnail_path
    elif file_ext in video_extensions:
        output=None
        try:
            cmd = ['ffprobe', '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height,duration,nb_frames,r_frame_rate',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output = result.stdout.splitlines()
            width = int(output[0])
            height = int(output[1])

            duration_str = str(output[2])
            if is_float(duration_str):
                duration = float(duration_str)
            else:
                duration = -1


            nb_frames = int(float(output[3])) if is_float(output[3]) else 0
            framerate_str = output[4]
            if is_float(framerate_str):
                framerate = float(framerate_str)
            else:
                framerate = -1
                if '/' in framerate_str:
                    num, denom = framerate_str.split('/')
                    if ((is_float(num)) and (is_float(denom))):
                        framerate = float(num) / float(denom) if float(denom) != 0 else 0.0

            with open(path, 'rb') as afile:
                buf = afile.read()
                hasher.update(buf)
            attributes["md5"]          = hasher.hexdigest()
            attributes["media_height"] = height
            attributes["media_width"]  = width
            attributes["duration"]     = duration
            attributes["length"]       = nb_frames
            attributes["framerate"]    = framerate

            thumbnail_path = make_thumbnaill(path)
            attributes["thumbnail"]    = thumbnail_path
        except Exception as e:
            print(f'error getting media attributes for {path}: {e}')
            print(output)
        
    
    return attributes

#queue stuff
class queue_item:
    def __init__(self):
        self.date = ""
        self.start_time = ""
        self.end_time = ""
        self.job_id = ""
        self.details = []
        self.source = ""
        self.complete_size = "" #completed size
        self.path = ""
        self.thumbnail = ""
        self.status = ""
        self.current_size = ""
    
    def create(
            self, date, start_time, end_time,
            job_id:int, details:list, size:str, path:str, thumbnail,
            status:str, post_id = None, current_size = ""):
        self.date       = date
        self.start_time = start_time
        self.end_time   = end_time
        self.job_id     = job_id
        self.details    = details
        self.source     = details[-1]
        self.source_printable = str(self.source)[7:17]+"..." + str(self.source)[-7:]
        self.complete_size       = size
        self.printable_size = format_size(size)
        self.path       =    path
        self.thumbnail  = thumbnail
        self.status     = status
        self.post_id    = post_id
        self.current_size = current_size

    def to_dict(self):
        return {
            'date': self.date,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'job_id': self.job_id,
            'details': self.details,
            'source' : self.source,
            'source_printable' : self.source_printable,
            'complete_size': self.complete_size,
            'printable_size' : self.printable_size,
            'path': self.path,
            'thumbnail': self.thumbnail,
            'status': self.status,
            'post_id': self.post_id,
            'current_size': self.current_size
        }
    def __repr__(self) -> str:
        return(str(self.to_dict()))

def delete_queueitem(job_id):
    logging.info(f"**UPLOADER** DELETE_ITEM|{job_id}|")

def get_queue():
    t=database.quicktimer("parse log")
    with open(database.log_path, 'r') as file:
        filedata = file.read()
    
    events = filedata.split('\n')
    events = [e.strip(';') for e in events if "**UPLOADER**" in e]
    t.finish()

    event_dicts = []
    t=database.quicktimer("preprocess")
    #preprocess event strings
    for event in events:
        date = event.split(' ')[0]
        time = event.split(' ')[1]
        event = event.split('** ')[-1]
        parts = event.split('|')
        event_type = parts[0].strip(" ")
        job_id = parts[1]
        details = parts[2:]

        event_dict = {
            "date": date,
            "time": time,
            'event_type': event_type,
            'job_id': job_id,
            'details': details
        }
        event_dicts.append(event_dict)
    t.finish()

    queue = {
        'unprocessed' : event_dicts,
        'ongoing': [],
        'completed': [],
        'errors': []
    }
    t=database.quicktimer("collect finished events")
    for event in event_dicts:
        #group events by job id, add to unprocessed until completed or error
        event_type = event["event_type"]
        if event_type == "COMPLETE":
            job_id = event["job_id"]
            full_job = [x for x in queue['unprocessed'] if x["job_id"] == job_id]
            event_types = [x['event_type'] for x in full_job]
            image_path = event['details'][0]
            
            thumbnail_path=f'{dataset_dir}/thumbnails/{job_id}.png'
            if ((database.keep_thumbnails == True) and os.path.isfile(thumbnail_path)):
                thumbnail = url_for('media', filename=thumbnail_path)
            else:   
                thumbnail = make_thumbnaill(image_path, to_link=True, name=job_id)

            remove_post = True if (("SAVE_POST" in event_types) or ("DELETE_ITEM" in event_types)) else False
            if ((thumbnail == "") or remove_post):
                #remove from queue
                queue['unprocessed'] = [x for x in queue['unprocessed'] if x["job_id"] != job_id]
                #delete file
                if os.path.isfile(image_path):
                    os.remove(image_path)

                continue
            #print(thumbnail, '\n\n')

            job = queue_item()
            job.create(
                full_job[0]['date'],
                full_job[0]['time'],
                event['time'],
                job_id,
                full_job[0]['details'],
                full_job[1]['details'][-1],
                image_path,
                thumbnail,
                event_type,
                0
                )

            queue['completed'].append(job)
            queue['unprocessed'] = [x for x in queue['unprocessed'] if x["job_id"] != job_id]
        elif event_type == "ERROR":
            job_id = event["job_id"]
            full_job = [x for x in queue['unprocessed'] if x["job_id"] == job_id]
            
            job = queue_item()
            job.create(
                date = full_job[0]['date'],
                start_time = full_job[0]['time'],
                end_time = event['time'],
                job_id = job_id,
                details = full_job[0]['details'],
                size="0 bytes",
                path="",
                thumbnail="",
                status=event_type)

            queue['errors'].append(job)
            queue['unprocessed'] = [x for x in queue['unprocessed'] if x["job_id"] != job_id]
        elif ((event_type == "finalize") or (event_type == "save_post")):
            pass
    t.finish()
    t=database.quicktimer("collect unfinished events")
    for event in queue['unprocessed']:
        job_id = event["job_id"]
        event_type = event["event_type"]
        full_job = [x for x in queue['unprocessed'] if x["job_id"] == job_id]
        if ((len(full_job) <= 2)): break

        size = full_job[1]['details'][-1]
        size = str(size.strip('bytes'))
        if not size.isdigit(): size = 'error'

        current_size = full_job[-1]['details'][-1]
        current_size = str(current_size.strip('bytes'))
        if not current_size.isdigit(): current_size = 'error'

        job = queue_item()
        job.create(
            full_job[0]['date'],
            full_job[0]['time'],
            "",
            job_id,
            full_job[0]['details'],
            size,
            "",
            "",
            event_type,
            current_size=current_size
            )
        
        queue['unprocessed'] = [x for x in queue['unprocessed'] if x["job_id"] != job_id]
        queue['ongoing'].append(job)
    t.finish()
    #cleanup - remove duplicate jobs by job_id (queue_item instances are not hashable)
    def _dedupe_jobs(jobs):
        seen = set()
        out = []
        for j in jobs:
            # support both queue_item instances and fallback dict-like items
            jid = getattr(j, 'job_id', None)
            if jid is None:
                try:
                    jid = j.get('job_id')
                except Exception:
                    jid = None
            if jid is None:
                out.append(j)
                continue
            if jid in seen:
                continue
            seen.add(jid)
            out.append(j)
        return out

    queue['ongoing']   = _dedupe_jobs(queue['ongoing'])
    queue['completed'] = _dedupe_jobs(queue['completed'])
    queue['errors']    = _dedupe_jobs(queue['errors'])
    #print(queue['ongoing'], '\n', queue['unprocessed'])
     
    #[print(x.to_dict()) for x in [*queue['ongoing'], *queue['completed'], *queue['errors']]]
    return queue


def format_size(initial_size: str) -> str:
    import re
    initial_size = re.sub(r'\D.+', '', initial_size)
    initial_size = "0" if initial_size == "" else initial_size
    size: float = float(initial_size)

    units = ['B', 'kB', 'MB', 'GB']
    i = 0
    while size >= 1000:
        size = size/1000
        i += 1
    unit = units[i]
    return(f'{round(size,2)}{unit}')

#post functions
class post:
    highest_id = int(database.get_next_id())
    def __init__(self, creation_date=time.time(), modified_date = time.time(), post_id = None,
                is_hidden = False, parent_id = "", children = [],
                score = 0, fav = False, views = 0, sources = [], rating = "", tag_string="",
                title="", description="", filepath="", file_ext=None, file_size=None,
                md5=None, media_height=None, media_width=None, duration=None, length=None,
                framerate=None, thumbnail_path="", job_id="", deleted=False) -> None:
        #general
        self.job_id = job_id
        if post_id == None:
            self.id = str(post.highest_id)
            post.highest_id += 1
        else:
            self.id = post_id
        self.creation_date: float = creation_date
        self.modified_date: float = modified_date
        self.is_hidden: bool = is_hidden
        self.parent_id: str = parent_id
        self.children: list = children
        #user
        self.score: int = score
        self.fav: bool = fav
        self.views: int = views
        #details
        self.sources: list = sources
        self.rating: str = rating
        self.tag_string: str = tag_string
        self.tag_list: list = [x.lower() for x in tag_string.split()]
        self.title: str = title
        self.description: str = description
        #file stuff
        new_filepath: str = os.path.normpath(filepath.strip("'"))
        self.filepath: str = new_filepath
        regenerate_thumbnail = ((not os.path.isfile(thumbnail_path)) and (filepath != ""))
        if regenerate_thumbnail:
            thumbnail_path = make_thumbnaill(filepath, name=str(self.id))
        self.thumbnail_path = thumbnail_path
        self.thumbnail_link = url_for('media', filename=thumbnail_path)
        self.deleted = deleted
        #media_stuff
        self.file_ext = file_ext
        if file_ext in image_extensions:
            self.file_type = 'image'
        elif file_ext in video_extensions:
            self.file_type = 'video'
        else:
            self.file_type = 'unknown'

        self.file_size = file_size
        self.md5 = md5
        self.media_height: int|float|None = media_height
        self.media_width: int|float|None = media_width
        self.duration: int|float|None = duration
        self.length: int|float|None = length
        self.framerate: int|float|None = framerate
        #
        media_attrs = [file_ext, file_size, md5, media_height,
                       media_width, duration, length, framerate]
        media_attr_exists = all([x!=None for x in media_attrs])
        generate_media_attr = False if ((filepath != "") and (media_attr_exists)) else True
        if generate_media_attr == True:
            #print('generating new media attributes')
            media_attributes = get_media_attributes(filepath)
            #print(media_attributes)
            self.file_ext = media_attributes['file_ext']
            self.file_size = media_attributes['file_size']
            self.md5 = media_attributes['md5']
            self.media_height = media_attributes['media_height']
            self.media_width = media_attributes['media_width']
            self.duration = media_attributes['duration']
            self.length = media_attributes['length']
            self.framerate = media_attributes['framerate']

    @staticmethod
    def from_dict(post_dict: dict) -> 'post':
        '''
        load post from dict
        Docstring for load
        
        :return: Description
        :rtype: post
        '''
        sources = post_dict.get('sources', [])
        if type(sources) == str:
            sources = sources.split(" ")
        
        post_obj = post(
            job_id = post_dict.get('job_id', ""),
            post_id = post_dict.get('id', ""),
            creation_date = post_dict.get('creation_date', ""),
            modified_date = post_dict.get('modified_date', ""),
            is_hidden = post_dict.get('is_hidden', False),
            parent_id = post_dict.get('parent_id', ""),
            children = post_dict.get('children', []),
            score = post_dict.get('score', 0),
            fav = post_dict.get('fav', False),
            views = post_dict.get('views', 0),
            sources = sources,
            rating = post_dict.get('rating', ""),
            tag_string = post_dict.get('tag_string', ""),
            title = post_dict.get('title', ""),
            description= post_dict.get('description', ""),
            filepath = post_dict.get('filepath', ""),
            thumbnail_path = post_dict.get('thumbnail_path', ""),
            file_ext = post_dict.get('file_ext', None),
            file_size = post_dict.get('file_size', None),
            md5 = post_dict.get('md5', None),
            media_height = post_dict.get('media_height', None),
            media_width = post_dict.get('media_width', None),
            duration = post_dict.get('duration', None),
            length = post_dict.get('length', None),
            framerate = post_dict.get('framerate', None),
            deleted= post_dict.get('deleted', False)
        )

        return post_obj
    def save(self, ignore_media=False):
        '''
        saves post to post table with it's values
        
        :param self: Description
        '''
        #save post media to database
        media_path = self.filepath
        final_path = media_path
        if ignore_media == False:
            if (not os.path.isfile(media_path)):
                print(f'error (while saving post), media file not found for post {self.id}: {media_path}')
                return
            t=database.quicktimer("get path/name")
            final_path = database.add_file('posts', f'{self.id}.{self.file_ext}', data = b'', just_path=True)
            t.finish()
            #print(f'\n\n{media_path} to be named {self.id}.{self.file_ext} -> {final_path}\n\n')
            t=database.quicktimer("move_file")
            os.replace(media_path, final_path)
            self.filepath = final_path
            t.finish()
        #save post data to database
        t=database.quicktimer("add to post table")
        json_data = self.to_dict()
        database.add_post_entry(final_path, json_data)
        t.finish()
        logging.info(f"**UPLOADER** SAVE_POST |{self.job_id}|{media_path}->{self.filepath}|{self.id}")

    def delete(self):
        print(f'deleting post: {self.id}')
        media_path = self.filepath
        os.remove(media_path)
        os.remove(self.thumbnail_path)
        self.deleted = True
        self.save(ignore_media=True)

    def isvalid(self) -> bool:
        if self.id == "":
            return False
        if os.path.isfile(self.filepath) == False:
            return False
        return True
    def to_dict(self) -> dict:
        post_dict = {
            'job_id': self.job_id,
            'id': self.id,
            'creation_date': self.creation_date,
            'modified_date': self.modified_date,
            'is_hidden': self.is_hidden,
            'parent_id': self.parent_id,
            'children': self.children,
            'score': self.score,
            'fav': self.fav,
            'views': self.views,
            'sources': self.sources,
            'rating': self.rating,
            'tag_string': self.tag_string,
            'tag_list' : self.tag_list,
            'title': self.title,
            'description': self.description,
            'filepath': self.filepath,
            'thumbnail_path': self.thumbnail_path,
            'file_ext': self.file_ext,
            'file_type' : self.file_type,
            'file_size': self.file_size,
            'md5': self.md5,
            'media_height': self.media_height,
            'media_width': self.media_width,
            'duration': self.duration,
            'length': self.length,
            'framerate': self.framerate,
            'deleted' : self.deleted
        }
        return post_dict
    def __repr__(self) -> str:
        valid = self.isvalid()
        if valid:
            s = f'post-{self.id}, tags:{self.tag_string}'
        else:
            s = f'invalid post'
        return s
    
def tag_summary(posts: list[post]) -> dict[str,int]:
    '''
    creates a dict listing details of the tags contained in a list of post objects
    
    :param posts: Description
    :type posts: list[post]
    :return: Description
    :rtype: dict[Any, Any]
    '''
    tag_dict = {"total tags":0}
    for post_obj in posts:
        if type(post_obj) != post:
            continue
        tag_list = post_obj.tag_string.split(' ')
        for tag in tag_list:
            tag = tag.lower()
            if tag in tag_dict.keys():
                tag_dict[tag] += 1
            else:
                tag_dict.update({tag : 1})

    tag_dict = dict(sorted(tag_dict.items(), key=lambda x: int(x[1]), reverse=True))
    return tag_dict
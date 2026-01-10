#this is the base module/file, to avoid circular imports, this should import no internal modules
import os, shutil, re, logging, json, time
'''
Database structure
0: monolithic, 1 folder, 1 table
1: static chunks, multiple folders with a set amount of posts each, 1 table per folder
2: binary tree, each chunk can have two subchunks or any amount of posts, 1 table per end-chunk
chunking strategy, decides what files go into newly create chunks when the current chunk is full
0: no files moved, just create new chunks as needed
1: try to keep file size of chunks similar
'''
database_structure = 0
chunk_size = 2000 #only for structure 1 and 2
chunking_strategy = 0

keep_thumbnails = True #greatly reduces load time at expense of database size

def get_parent(path: str) -> str :
    parent = os.path.split(path)[0]
    return parent
def get_source_dir():
    path = get_parent(get_parent(os.path.abspath(__file__)))
    return os.path.normpath(path)

source_dir = get_source_dir()
config_path = f'{source_dir}/config.json'
def get_setting(setting_key:str):
    with open(config_path) as f:
        config = dict(json.load(f))

    keys = config.keys()
    if not (setting_key in keys):
        raise KeyError(f'setting {setting_key} not in config keys')
    return config[setting_key]

dataset_dir = get_setting('dataset_path')
post_table_path = f'{dataset_dir}/post_table.json'
tag_detail_table_path = f'{dataset_dir}/tag_detail_table.json'

temp_dir = f'{source_dir}/static/temp/'
log_path = f'{dataset_dir}/database_log.txt'

posts_per_page = 20

tag_detail_table_preset = {
    "tags": [],
    "tag_count" : 0
}
post_table_preset = {
    "posts": {},
    "post_count": 0
}
post_entry_preset = {
            'id': "",
            'creation_date': "",
            'modified_date': "",
            'is_hidden': False,
            'parent_id': "",
            'children': [],
            'score': 0,
            'fav': False,
            'views': "",
            'sources': [],
            'rating': "",
            'tag_string': "",
            'title': "",
            'description': "",
            'filepath': "",
            'file_ext': "",
            'file_size': 0,
            'md5': "",
            'media_height': 0,
            'media_width': 0,
            'duration': 0,
            'length': 0,
            'framerate': 0,
            'thumbnail': ""
        }

##
def create_table(table_path: str, preset: dict):
    if not os.path.isfile(table_path):
        import json
        with open(table_path, 'w', encoding='utf-8') as f:
            json.dump(preset, f, indent=4)

def escape_path(path:str, remove = True, replace = False) -> str:
    try:
        dir, name = os.path.split(path)
    except SyntaxError:
        split_str = path.split('\\')
        dir = '\\'.join(split_str[:-1])
        name = split_str[-1]
    sub = '++' if replace else ''
    esc_name = re.sub(r'[\/\\\:\*\<\>\?\"\|]+', sub, name)
    esc_path = os.path.join(dir, esc_name)
    esc_path = os.path.normpath(esc_path)
    #print(f'path:{path} -> escaped path: {esc_path}')
    return esc_path

##
def destroy_database():
    # stop logging and close handlers so the log file can be removed
    try:
        root_logger = logging.getLogger()
        for h in root_logger.handlers[:]:
            try:
                h.close()
            except Exception:
                pass
            root_logger.removeHandler(h)
        logging.shutdown()
    except Exception:
        pass

    #delete dataset directory and all contents
    if os.path.isdir(dataset_dir):
        shutil.rmtree(dataset_dir)

    # re-enable logging (will recreate the log file when next written)
    logging.basicConfig(filename=log_path, level=logging.INFO, format=log_format)
    
def initialize_database(reset=False):
    if reset:
        destroy_database()
    os.makedirs(dataset_dir, exist_ok=True)

    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    if database_structure == 0:
        initialize_monolithic_database()
    elif database_structure == 1:
        initialize_static_chunk_database()
    elif database_structure == 2:
        initialize_binary_tree_database()

def initialize_monolithic_database():
    #tree = ['posts', 'incomplete', 'thumbnails'] #
    os.makedirs(f'{dataset_dir}/posts', exist_ok=True)
    os.makedirs(f'{dataset_dir}/incomplete', exist_ok=True)#for media downloaded but not yet posted
    os.makedirs(f'{dataset_dir}/thumbnails', exist_ok=True)

    create_table(post_table_path, post_table_preset)
    create_table(tag_detail_table_path, tag_detail_table_preset)
    return
def initialize_static_chunk_database():
    return
def initialize_binary_tree_database():
    return
##
from werkzeug import datastructures
def add_file_to_queue(file: datastructures.FileStorage):
    job_id = str(time.time()).replace('.', '')
    filename = file.filename
    assert type(filename) == str
    extension = filename.split('.')[-1]
    filepath = temp_dir + filename
    
    file.save(filepath)
    filesize = os.path.getsize(filepath)

    msg1 = f'**UPLOADER** START|{job_id}|{filepath}|From_Computer'
    logging.info(msg1)
    msg2 = f'**UPLOADER** START-DOWNLOAD|{job_id}|From_Computer|{filesize}bytes'
    logging.info(msg2)
    
    final_path = add_file('incomplete', f'{job_id}.{extension}', data=b'')
    os.replace(filepath, final_path)

    msg3 = f'**UPLOADER** COMPLETE|{job_id}|{final_path}|post_id'
    logging.info(msg3)

def add_file(sub_dir: str, filename: str, data: bytes, autopath=True, path="", just_path=False) -> str:
    '''
    adds media file to database
    
    :param sub_dir: what sub diretory the file belongs in: posts, incomplete, thumbnails
    :type sub_dir: str
    :param filename: if filename == auto... :automatically assign a filename
    :type filename: str
    :param data: Description
    :type data: bytes
    :param autopath: Description
    :type autopath: bool
    :param path: unescaped!
    :type path: str
    :param just_path: only return path without writing file
    :type just_path: bool
    '''
    def autoname_file(dir: str) -> str:
        from helpers import is_float
        if os.path.isdir(dir) == False: raise NotADirectoryError(f'{dir} not found')
        dir_list = os.listdir(dir)
        filtered = [int(os.path.splitext(x)[0].strip('.')) 
                    for x in dir_list 
                    if (is_float(os.path.splitext(x)[0]))]
        filtered.append(-1)
        name = str(max(filtered)+1)
        return name

    final_path = "path_not_set"
    autoname = True if filename.startswith('auto') else False

    if type(data) != bytes:
        if type(data) == str:
            data = data.encode('utf-8')
        elif type(data) == dict:
            data = json.dumps(data).encode('utf-8')
        else:
            data = bytes(data)
    

    if database_structure == 0:
        #get final path
        if ((autopath) or (path == "")):
            if not sub_dir in ['posts', 'incomplete', 'thumbnails']:
                print(f'file_type: {sub_dir}, is unmatched, setting to incomplete')
                sub_dir = 'incomplete'
            path_head = f'{dataset_dir}/{sub_dir}/'

            if autoname:
                ext = os.path.splitext(filename)[-1]
                filename = autoname_file(path_head) + ext
            filename = escape_path(filename)

            final_path = f'{dataset_dir}/{sub_dir}/{filename}'
        else:
            final_path = path

    elif database_structure == 1:
        if autopath:
            pass
        else:
            pass
    elif database_structure == 2:
        if autopath:
            pass
        else:
            pass

    final_path = os.path.normpath(final_path)
    if not just_path:
        try:
            with open(final_path, 'wb') as f:
                f.write(data)
        except Exception as e:
            print(f'error writing file to database: {repr(e)}')
    return final_path
#
def add_post_entry(media_path: str, entry: dict):
    '''
    add a post entry to the post table

    :param entry: Description
    :type entry: dict
    '''
    import json
    with open(post_table_path, 'r', encoding='utf-8') as f:
        post_table = json.load(f)
    post_table['posts'].update({str(entry['id']):entry})
    post_table['post_count'] += 1
    with open(post_table_path, 'w', encoding='utf-8') as f:
        json.dump(post_table, f, indent=4)
#
def get_post(post_id):
    '''
    take an id of a post and return a post obj, or none if failure\n

    :return: post_obj
    :rtype: helpers.post
    '''
    if type(post_id) == str:
        post_id = post_id.strip()
    elif type(post_id) == int:
        post_id = str(post_id).strip()
    else:
        print(f'invalid post_id: {post_id}')
        return
    
    with open(post_table_path, 'r', encoding='utf-8') as f:
        post_table = dict(json.load(f)['posts'])
    post_dict = post_table.get(post_id)
    if post_dict == None:
        print(f'post id {post_id} not found in post table')
        return
    
    from helpers import post as post_class
    post_obj = post_class.from_dict(post_dict)

    return post_obj
##
def filter_posts(query: str, page: int = 0, num_returned: int = posts_per_page, fix_posts=True) -> list:
    '''
    Filter posts based on a query string. \n
    query syntax: "tag1 tag2 ... tagn key:value key:value ... key:value" \n
    query is treated as a logic statment, defaults to AND between terms \n
    ex. "cat cute (-dog or score:<10)" means posts must have tags "cat" and "cute", but not have tag "dog" or have score less than 10
    
    :param query: Description
    :type query: str
    :param quantity: Description
    :type quantity: int
    :return: Description
    :rtype: list[post_class]
    '''
    from helpers import post as post_class

    def check_post(post_obj: "post_class", query: dict) -> bool:
        valid = True
        allow_deleted = False
        if (allow_deleted == False) and (post_obj.deleted == True):
            return False
        for tag in query['tags']:
            if not (tag in post_obj.tag_list):
                return False
            
        return valid

    #get post_table
    with open(post_table_path, 'r', encoding='utf-8') as f:
        post_table = json.load(f)['posts']
    assert type(post_table) == dict
    post_table = list(post_table.values())

    #parse query
    query = query.strip()
    query_list = query.split(' ')
    query_dict = {"tags":[], "sort_query": 'id'}
    for condition in query_list:
        if ':' in condition:
            if ("sort" in condition) or ("order" in condition):
                query_dict['sort_query'] = condition.split(":")[-1]
        else:
            query_dict['tags'].append(condition.strip('-').lower())
    query_dict['tags'] = [tag for tag in query_dict['tags'] if len(tag)>0]

    #get matching posts
    matched_posts = []
    
    total_posts = len(post_table)
    required_posts = min(total_posts, num_returned + page*posts_per_page)
    #print(f"page={page} -> t:{total_posts}, r:{required_posts}, n:{num_returned}")

    post_table.reverse()
    for post_dict in post_table:
        if len(matched_posts) >= required_posts:
            break
        #load post
        post_obj = post_class.from_dict(post_dict)
        if fix_posts:
            #checks if a post needed fixing, if so, saves it
            new_post_dict = post_obj.to_dict()
            if post_dict != new_post_dict:
                #print(f'\nold post dict: {post_dict}\nnew post dict: {new_post_dict}\n')
                post_dict = new_post_dict
                post_obj.from_dict(post_dict)
                post_obj.save()
        
        if check_post(post_obj, query_dict):
            matched_posts.append(post_obj)
    #sort
    from operator import attrgetter
    def int_attr(name):
        getter = attrgetter(name)
        return lambda p: int(getter(p))

    function_dict = {
        'id': int_attr('id'),
        'score': int_attr('score'),
        'views': int_attr('views'),
        'file_size': int_attr('file_size'),
        'height' : int_attr('media_height'),
        'width' : int_attr('media_width'),
    }
    sort_function = function_dict.get(query_dict['sort_query'], int_attr('id'))
    matched_posts.sort(key=sort_function, reverse=True)

    matched_posts = matched_posts[page*posts_per_page : num_returned + page*posts_per_page] #return paged slice
    return matched_posts

def get_next_id() -> str:
    from helpers import is_float
    if database_structure == 0:
        dir_path = f'{dataset_dir}/posts/'
    else:
        dir_path = ""
    dir_list = os.listdir(dir_path)
    filtered = [int(os.path.splitext(x)[0].strip('.')) 
                for x in dir_list 
                if (is_float(os.path.splitext(x)[0]))]
    filtered.append(-1)
    name = str(max(filtered)+1)
    return name

class quicktimer:
    timers = []
    def __init__(self, name=""):
        import time
        self.start_time = time.time()
        self.name = name
        quicktimer.timers.append(self)

    def finish(self, digits=1):
        '''
        prints time elapsed since this object was initalized
        
        :param self: Description
        :param digits: Description
        '''
        
        spaces = ''.rjust((len(quicktimer.timers)-1)*1)

        import time
        end = time.time()
        total_time = round((end-self.start_time)*1000, digits)
        print(f'{spaces}{self.name}: {total_time}ms')
        quicktimer.timers.remove(self)
        return total_time
    @staticmethod
    def finish_all(digits=1):
        for timer in quicktimer.timers:
            assert type(timer) == quicktimer
            timer.finish()

def log_info(caller:str, arg_dict:dict):
    arg_string = '|'.join([f'{key}={val}' for key, val in arg_dict.items()])
    msg = f'**{caller}** {arg_string}'
    logging.info(msg)

initialize_database()
#setup logging
with open(log_path, 'a', encoding='utf-8') as f:
    f.write('\n\n----- New Session -----\n')
log_format = '%(asctime)s - %(levelname)s - %(message)s;'
logging.basicConfig(filename=log_path, level=logging.INFO, format=log_format, force=True)
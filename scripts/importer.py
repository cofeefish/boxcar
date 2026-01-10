import requests, os, logging, re, time, threading
import database
import urllib.parse as parse

#project wide vars
dataset_dir = database.dataset_dir
source_dir = database.source_dir
temp_dir = database.temp_dir
post_table_path = database.post_table_path

source_splitter_str = "+++"

#sites with an impelmented api
apis = []
#
max_workers = 4
blacklist = ['logo', 'icon', '.js', 'avatar',
            'thumbnail', 'watermark',
            'banner', 'profile', '.svg']
image_extensions = ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'svg', 'gif']
video_extensions = ['mp4', 'webm', 'avi', 'flv', 'mov', 'wmv', 'mkv', 'm4v']

#small helpers

def escape_str(self: str) -> str:
    escaped = self.replace("&", "&amp;").replace(";", "&lt;").replace(">", "&gt;")
    return escaped

def get_and_check_response(url, stream = False):
    try:
        parsed_uri = parse.urlparse(url)
        assert type(parsed_uri) == parse.ParseResult

        scheme_len = len(parsed_uri.scheme)
        if scheme_len == 0:
            raise RuntimeError()
            
    except RuntimeError:
        print(f'invalid url: {url}')
        return None
    base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
    headers = {
        'User-Agent' : 'BoxcarScraper/0.1 ',
        'priority' : 'u=0, i',
        'referer' : base_domain
    }
    response = requests.get(url, stream=stream, headers=headers)
    if response.status_code == 200:
        return response
    elif response.status_code == 403:
        raise RuntimeError(f'unable to download a file from url: {url}, due to site restrictions, http: 403')
    elif response.status_code == 404:
        raise RuntimeError(f'unable to download a file from url: {url}, site not found, http: 404')
    else:
        raise RuntimeError(f"182|unable to download file from url: {url}, wrong code recived: {response.status_code}")

#media functions
def save_media_from_url(path: str, name = "", sources = []):
    '''
    recursively search for and save media files from a url
    
    :param path: Description
    :type path: str
    :param name: Description
    :param file: Description
    :param sources: list fo sources that lead to a file, last one is the final file
    :type sources: list
    '''
    def is_media_url(parsed_uri: parse.ParseResult)->bool:
        url_extension = parsed_uri.path.split('.')[-1]
        if (url_extension in image_extensions or url_extension in video_extensions):
            return True
        
        exception_pairs = [("pixeldrain.com", "/api/file/")]
        for netloc, path in exception_pairs:
            if (parsed_uri.netloc == netloc) and (parsed_uri.path.startswith(path)):
                return True
        return False

    def save_file_subroutine(path: str, job_id: str, sources: list):
        filepath = path
        extension = ""
        url = str(sources[-1]).strip('#')
        try:
            if job_id == "":
                raise RuntimeError("no job id specified")
            logging.info(f"**UPLOADER** START|{job_id}|{path}|{source_splitter_str.join(sources)}")
            parsed_uri = parse.urlparse(url)
            url_is_valid = True if (
                parsed_uri.scheme != "" and
                parsed_uri.netloc != ""
            ) else False

            if url_is_valid:
                media_found = False

                extension = url.split('.')[-1].lower()
                if not ('https://' in url or 'http://' in url):
                    url = "http://" + url
                if is_media_url(parsed_uri):
                    print('media link, downloading directly')
                    response = get_and_check_response(url, stream=True)
                    if response == None: 
                        raise RuntimeError(f"unable to download file from url: {url}, invalid url")
                    filepath = f'{path}.{extension}'

                    chunk_size = 2048
                    total_size = int(response.headers.get('content-length', 0))
                    bytes_downloaded = 0
                    
                    indices = 4
                    index = 0
                    if total_size == 0: raise FileNotFoundError('media downloaded is zero bytes')
                    logging.info(f"**UPLOADER** START-DOWNLOAD|{job_id}|{source_splitter_str.join(sources)}|{total_size}bytes")
                    z = total_size // (indices + 1)
                    with open(filepath, 'wb') as media_file:
                        for chunk in response.iter_content(chunk_size):
                            media_file.write(chunk)
                            bytes_downloaded += len(chunk)
                            new_index = bytes_downloaded // z
                            if new_index != index:
                                logging.info(f"**UPLOADER** PROGRESS|{job_id}|{bytes_downloaded}bytes")
                                index = new_index
                    media_found = True
                else:
                    #try to find media in page
                    response = get_and_check_response(url)
                    if response == None:
                        raise RuntimeError(f"unable to download file from url: {url}, invalid url")
                    html = response.text
                    media_urls = get_media_urls(html)
                    
                    semaphore = threading.Semaphore(max_workers)
                    threads = []
                    for i, sub_url in enumerate(media_urls):
                        sub_path = f'{path}_{i}'
                        sub_job_id = f'{job_id}_{i}'

                        sub_sources = sources + [sub_url]

                        def worker(p=sub_path, jid=sub_job_id, sources: list =sub_sources):
                            try:
                                save_file_subroutine(p, jid, sources)
                            finally:
                                semaphore.release()

                        semaphore.acquire()
                        thread = threading.Thread(target = worker)
                        threads.append(thread)
                        thread.start()

                if not media_found:
                    raise RuntimeError(f"unable to download file from url: {url}, no media found")
            else:
                raise RuntimeError("no valid url or file")
            
            #MOVE FILE TO FINAL LOCATION
            assert os.path.isfile(filepath), "file not found after download"
            assert extension != "", "file has no extension"
            final_path = database.add_file('incomplete', f'{job_id}.{extension}', data=b'')
            os.replace(filepath, final_path)
            logging.info(f'**UPLOADER** COMPLETE|{job_id}|{final_path}|post_id')
        except Exception as e:
            message = f'**UPLOADER** ERROR|{job_id}|{e}'
            print(message)
            logging.error(message)
    
    def get_media_urls(html: str) -> list[str]:
        """Extracts inner HTML of media elements from the provided HTML string."""
        html = re.sub(r'[\n]', ' ', html)#remove new lines
        pattern = re.compile(r'(<img.*?>)|(<video[\s\S]*?</video>)|(<meta property="og:image".*?>)')
        media_htmls = [str(''.join(x)) for x in re.findall(pattern,html)]

        media_sources = []
        for media in media_htmls:
            if any([x in media.lower() for x in blacklist]):
                ##print(f'skipping media with blacklisted content: {media}')
                continue
            media_src = re.search(r'src="(.*?)"|content="(.*?)"', media)
            if media_src == None:
                continue
            media_src = media_src.group(1) if media_src.group(1) != None else media_src.group(2)
            media_sources.append(media_src)
        return media_sources

    job_id = str(time.time()).replace('.', '')
    name = os.path.basename(path) if name == "" else name
    name = escape_str(name)

    thread = threading.Thread(target = save_file_subroutine, args = (path, job_id, sources))
    thread.start()
    return

#tag functions
def get_tags_from_many_url(urls: list[str], end_type:str="str") -> list[str]|str:
    '''
    get all tags from a list of urls \n
    if nothing in the bottom (last) url is found, it moves up in the urls until it sucseeds
    
    :param urls: Description
    :type urls: list
    :return: Description
    :rtype: list[Any]
    '''

    def danbooru_tag_function(html) -> list:
        tags = re.findall(r'<(.*?tags.*?)>', html)
        tags = [tag for tag in tags if tag.startswith('section')]#gets tags element
        if len(tags) == 0:
            return []
        tags = re.findall(r'"(.*?)"', tags[0])#gets all tags in the element
        tags = sorted(tags, key=lambda x: len(re.sub(r'[^ ]', '', x)) if (x != None) else 0, reverse=True)[0] #find the tag with the most spaces
        assert type(tags) == str
        tags = tags.split(' ')
        #[print(tag) for tag in tags]
        return tags
    def realbooru_tag_function(html)-> list:
        tags = re.findall(r'<.*?href="index\.php\?page=post&amp;s=list&amp;tags=.*?">(.*?)</a>', html)
        if len(tags) == 0:
            return []
        #[print(tag) for tag in tags]
        return tags
    def general_tag_function(html)-> list:
        return []
    tag_functions = {
        'danbooru' : danbooru_tag_function,
        'realbooru' : realbooru_tag_function,
        'general' : general_tag_function
    }
    
    def get_tags_from_single_url(url:str) -> list[str]:
        from helpers import rank_similarity
        t=database.quicktimer("get html")
        html = get_and_check_response(url)
        t.finish()
        if html == None: return []
        html = html.text

        #order function by which one is probably the best for this url
        parsed_uri = parse.urlparse(url)
        base_domain = parsed_uri.netloc
        function_keys = rank_similarity(base_domain, list(tag_functions.keys()))
        function_keys = [x[0] for x in function_keys]

        for function_key in function_keys:
            t=database.quicktimer(f'{function_key} - tags')
            tag_function = tag_functions[function_key]
            new_tags = tag_function(html)
            t.finish()
            if len(new_tags) > 0:
                return new_tags
        return []

    assert type(urls) == list, TypeError('url list was not a list')
    urls = [str(url) for url in urls if str(url)!=""]
    #remove suspected media urls to save time:
    urls = [
        url for url in urls if not (
            url.split('.')[-1] in image_extensions + video_extensions
        )
    ]
    tags = []

    urls.reverse()
    for url in urls:
        new_tags = get_tags_from_single_url(url)
        if len(new_tags) > 0:
            tags = new_tags
            break

    if end_type != "list":
        tags = [re.sub(r'\s+', '_', tag) for tag in tags]
        tags = ' '.join(tags)
    return tags

"""
import importer
link = "https://realbooru.com/index.php?page=post&s=view&id=912371"
importer.get_tags_from_many_url([link])
"""
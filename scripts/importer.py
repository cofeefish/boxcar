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
video_extensions = ['mp4', 'webm', 'avi', 'flv', 'mov', 'wmv', 'mkv', 'm4v', 'mpeg']

#small helpers

def escape_str(self: str) -> str:
    escaped = self.replace("&", "&amp;").replace(";", "&lt;").replace(">", "&gt;")
    return escaped

def unescape_str(self: str) -> str:
    unescaped = self.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return unescaped

def get_and_check_response(url, stream = False):
    url = unescape_str(url)
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


class urlTreeNode:
    def __init__(self, url: str):
        self.url = url
        self.children = []
    def add_child(self, child_node):
        self.children.append(child_node)

#media functions
def save_media_from_url(path: str, name = "", input_url_list = [], recursive = False):
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

    def add_file_to_queue_from_urls(path: str, job_id: str, media_pair_list: list):
        '''
        Docstring for add_file_to_queue_from_urls
        
        :param path: Description
        :type path: str
        :param job_id: Description
        :type job_id: str
        :param media_pair_list: Description of list of media pairs (url, path importer traversed)
        :type media_pair_list: list
        '''
        def save_file_subroutine(extension:str, path: str, job_id: str, url:str, parent_sources:list):
            filepath = f'{path}.{extension}'
            try:
                if job_id == "":
                    raise RuntimeError("no job id specified")
                logging.info(f"**UPLOADER** START|{job_id}|{path}|{source_splitter_str.join(parent_sources)}")
                parsed_uri = parse.urlparse(url)
                url_is_valid = True if (
                    parsed_uri.scheme != "" and
                    parsed_uri.netloc != ""
                ) else False

                if url_is_valid:
                    media_found = False

                    print(url)
                    extension = url.split('.')[-1].lower().split('?')[0]
                    if not ('https://' in url or 'http://' in url):
                        url = "http://" + url
                    if is_media_url(parsed_uri):
                        print('media link, downloading directly')
                        response = get_and_check_response(url, stream=True)
                        if response == None: 
                            raise RuntimeError(f"unable to download file from url: {url}, invalid url")

                        chunk_size = 2048
                        total_size = int(response.headers.get('content-length', 0))
                        bytes_downloaded = 0

                        indices = 4
                        index = 0
                        if total_size == 0: raise FileNotFoundError('media downloaded is zero bytes')
                        logging.info(f"**UPLOADER** START-DOWNLOAD|{job_id}|{source_splitter_str.join(parent_sources)}|{total_size}bytes")
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

                            print(len(parent_sources))
                            if len(parent_sources) == 1:
                                media_pair = (sub_url, [parent_sources[0], sub_url])
                            else:
                                media_pair = (sub_url, parent_sources[1] + [sub_url])

                            def worker(p=sub_path, jid=sub_job_id, media_pair=[media_pair]):
                                try:
                                    add_file_to_queue_from_urls(p, jid, media_pair)
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
                final_path = database.add_file('queue_storage', f'{job_id}.{extension}', data=b'')
                os.replace(filepath, final_path)
                logging.info(f'**UPLOADER** COMPLETE|{job_id}|{final_path}|post_id')
            except Exception as e:
                message = f'**UPLOADER** ERROR|{job_id}|{e}'
                print(message)
                logging.error(message)
        for i, media_pair in enumerate(media_pair_list): 
            end_url, parent_sources = media_pair
            end_url = str(end_url).strip('#')
            if end_url == "":
                raise RuntimeError("no valid url or file")
            filepath = os.path.join(temp_dir, f'temp_{job_id}')
            extension = end_url.split('.')[-1].lower().split('?')[0]
            save_file_subroutine(extension, path, f'{job_id}_{i}', end_url, parent_sources)
        sources_str_list = [str(media_pair[0]) for media_pair in media_pair_list]
        logging.info(f"**UPLOADER** ALL COMPLETE|{job_id}|{path}|{source_splitter_str.join(sources_str_list)}")

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

    #recursive stuff
    def get_post_urls(html: str) -> list[str]:
        """Extracts inner HTML of link elements from the provided HTML string."""
        html = re.sub(r'[\n]', ' ', html)  # remove new lines
        pattern = re.compile(r'(<a .*? href="(.*?)".*?>)')
        post_htmls = [str(''.join(x)) for x in re.findall(pattern, html)]

        post_sources = []
        for post in post_htmls:
            post_href = re.search(r'href="(.*?)"', post)
            if post_href is None:
                continue
            post_href = post_href.group(1)
            post_sources.append(post_href)
        return post_sources

    def recursive_search_subroutine(url: str, current_depth: int, depth_limit: int, checked_urls: set, path_stack: list):
        """Recursively build a url tree. Media collection is done after the tree is built."""
        if current_depth >= depth_limit:
            return None

        # resolve and normalize the url
        parsed_uri = parse.urlparse(url)
        if parsed_uri.scheme == "" or parsed_uri.netloc == "":
            return None

        # use the full url as the normalized form
        norm_url = parse.urlunparse(parsed_uri)
        if norm_url in checked_urls:
            return None
        checked_urls.add(norm_url)

        node = urlTreeNode(norm_url)

        try:
            response = get_and_check_response(norm_url)
            if response is None:
                return node
            html = response.text

            # find linked posts and recurse, resolving relative links
            post_urls = get_post_urls(html)
            for post_url in post_urls:
                full_post = parse.urljoin(norm_url, post_url)
                child_node = recursive_search_subroutine(full_post, current_depth + 1, depth_limit, checked_urls, path_stack + [full_post])
                if child_node is not None:
                    node.add_child(child_node)

        except Exception as e:
            print(f'error checking url {norm_url}: {e}')

        return node

    def collect_media_pairs_from_tree(root: urlTreeNode) -> list:
        """Traverse the URL tree, fetch media only for leaf nodes, and return media_pairs.

        Each media_pair is a tuple: (full_media_url, source_path_list)
        """
        media_pairs = []

        def dfs(node: urlTreeNode, path: list):
            '''Depth-first search to collect media URLs from leaf nodes.'''
            if node is None:
                return
            if len(node.children) == 0:
                try:
                    response = get_and_check_response(node.url)
                    if response is None:
                        return
                    html = response.text
                    media_urls = get_media_urls(html)
                    for m in media_urls:
                        full_media = parse.urljoin(node.url, m)
                        media_pairs.append((full_media, path.copy()))
                except Exception as e:
                    print(f'error collecting media for {node.url}: {e}')
            else:
                for child in node.children:
                    dfs(child, path + [child.url])

        dfs(root, [root.url])
        return media_pairs

    depth_limit = int(database.get_setting('recursive_upload_depth', 2))
    job_id = str(time.time()).replace('.', '')
    name = os.path.basename(path) if name == "" else name
    name = escape_str(name)

    if recursive:
        checked_urls = set()
        # build the url tree from the root
        url_tree = recursive_search_subroutine(input_url_list[0], 0, depth_limit, checked_urls, [input_url_list[0]])
        if url_tree is None:
            print(f'no pages found from recursive search of url: {path}')
            return

        # collect media pairs from leaf nodes of the tree
        media_pairs = collect_media_pairs_from_tree(url_tree)
        print(f'recursive search found {len(media_pairs)} media pairs from url: {path}')
        if len(media_pairs) == 0:
            print(f'no media found from recursive search of url: {path}')
            return

        new_path = os.path.join(temp_dir, f'recursive_{job_id}_{name}')
        thread = threading.Thread(target=add_file_to_queue_from_urls, args=(new_path, job_id, media_pairs))
    else:
        # Non-recursive: expect `sources` to be a list of source URLs where the last is the media URL
        if not isinstance(input_url_list, list) or len(input_url_list) == 0:
            raise RuntimeError('no valid sources provided for non-recursive download')
        media_url = input_url_list[-1]
        media_pairs = [[media_url, input_url_list]]
        thread = threading.Thread(target=add_file_to_queue_from_urls, args=(path, job_id, media_pairs))
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
    filtered_urls = [str(url) for url in urls if str(url)!=""]
    #remove suspected media urls to save time:
    urls = [
        url for url in filtered_urls if not (
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
    #print(f'found tags: {tags} from urls: {urls}')
    return tags


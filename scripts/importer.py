import requests, os, logging, re, time
import database
import urllib.parse as parse
from concurrent.futures import ThreadPoolExecutor

ytdlp = False
use_ytdlp = database.get_setting('use_ytdlp', False)
if use_ytdlp:
    ytdlp_whitelist = ['youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com']
    ytdlp_blacklist =[]
    import yt_dlp as ytdlp

#project wide vars
dataset_dir = database.dataset_dir
source_dir = database.source_dir
temp_dir = database.temp_dir
post_table_path = database.post_table_path

#optimization vars
verbose = False
larger_blacklist = True
ignore_mirrors = True

depth_limit = int(database.get_setting('recursive_upload_depth', 2))
source_splitter_str = "+++"
max_workers = 4
# executor for background downloads (downloads run concurrently with crawling)
download_executor = ThreadPoolExecutor(max_workers=max_workers)

#storage vars
apis = []
blacklist = ['logo', 'icon', '.js', 'avatar',
            'thumbnail', 'watermark',
            'banner', 'profile', '.svg', 'css', 'javascript']
if larger_blacklist:
    blacklist += ['tag', 'dmca', 'help', 'support', 'contact', 'about', 'privacy', 'terms',
                   'account', 'login', 'signup', 'register', 'tos', 'list', 'sample', 'wiki',
                   'artists', 'pools', 'forum', 'comment', 'explore', 'search', 'blog', 'news', 'users',
                   'iqdb_']
image_extensions = ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'gif']
video_extensions = ['mp4', 'webm', 'avi', 'flv', 'mov', 'wmv', 'mkv', 'm4v', 'mpeg']
'''
mirror_dict structure: {domain: [mirror_urls]}'''
mirror_dict = {
    'danbooru.donmai.us' : ['i.pximg.net', 'twitter.com', 'huqu.fanbox.cc', 'pawoo.net', 'www.pixiv.net', 'x.com', 'www.patreon.com', 'discord.gg'],
}

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
    def __init__(self, url: str, parent = None):
        self.tree_id = str(time.time()).replace('.', '')
        self.url = url
        self.children = []
        self.parent = parent
        self.checked = False
        self.is_media = is_media_url(url)

        # If this node is a root, create its own tree_dict; otherwise register
        # this node in the root's tree_dict and add to the parent's children.
        if parent is None:
            self.root = self
            self.tree_dict = {self.tree_id: self}
        else:
            self.root = parent.root
            parent.add_child(self)
            self.root.tree_dict[self.tree_id] = self

    def add_child(self, child_node):
        if child_node not in self.children:
            self.children.append(child_node)
            child_node.parent = self
            child_node.root = self.root
            # ensure child is registered in the root's index
            if not hasattr(self.root, 'tree_dict'):
                self.root.tree_dict = {}
            self.root.tree_dict[child_node.tree_id] = child_node

    def get_all_nodes(self) -> list:
        # Return all nodes in the current tree using DFS from the root.
        def dfs(node: urlTreeNode):
            nodes = [node]
            for child in node.children:
                assert type(child) == urlTreeNode
                nodes.extend(dfs(child))
            return nodes
        return dfs(self.root)
    def get_all_urls(self):
        return [node.url for node in self.get_all_nodes()]

    def path_to_root(self):
        path = []
        node = self
        while node is not None:
            path.append(node.url)
            node = node.parent
        return path[::-1]
    
    def get_all_edges(self):
        edges = []
        for node in self.get_all_nodes():
            for child in node.children:
                edges.append((node.url, child.url))
        return edges

#media functions
def is_media_url(url: str)->bool:
    '''Determines if a URL likely points directly to a media file or an API endpoint that can be extracted with ytdlp.'''
    #ends with file extension
    parsed_uri = parse.urlparse(url)
    url_extension = parsed_uri.path.split('.')[-1]
    if (url_extension in image_extensions or url_extension in video_extensions):
        return True
    
    #url is supported by ytdlp
    if use_ytdlp:
        if any([netloc in parsed_uri.netloc for netloc in ytdlp_whitelist]):
            return True
        
    #api endpoints that don't have a media file extension but can be return a media file
    exception_pairs = [("pixeldrain.com", "/api/file/")]
    for netloc, path in exception_pairs:
        if (parsed_uri.netloc == netloc) and (parsed_uri.path.startswith(path)):
            return True
    return False

def save_media_url(url: str, parent_sources = []):
    '''
    Saves media from a URL directly if it points to a media file, or uses ytdlp if it's a supported site.
    '''
    #helper functions for specific cases
    def save_direct_media(url: str, job_id: str, filepath: str) -> str:
        response = get_and_check_response(url, stream=True)
        if response is None:
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
        
        return filepath
    def save_with_ytdlp(url: str, job_id: str, filepath: str) -> str:
        if not ('https://' in url or 'http://' in url):
            url = "http://" + url

        path, extension = os.path.splitext(os.path.basename(url))
        # include job_id in filename to avoid collisions when downloading concurrently
        if extension:
            filepath_name = f"{path}_{job_id}.{extension}"
        else:
            filepath_name = f"{escape_str(url)}_{job_id}"
        filepath = os.path.join(temp_dir, filepath_name)

        print([(x, url, x not in url) for x in ytdlp_blacklist])
        if use_ytdlp and all([x not in url for x in ytdlp_blacklist]):
            ytdlp_opts = {
                'outtmpl': filepath,
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'noplaylist': True
            }
            assert type(ytdlp) != bool, "yt_dlp failed to import"
            with ytdlp.YoutubeDL(ytdlp_opts) as ydl: #type: ignore
                try:
                    info = ydl.extract_info(url, download=True)
                    extension = info.get('ext', '')
                    print(filepath, extension)
                    if extension and os.path.exists(filepath):
                        downloaded_file = f'{filepath}.{extension}'
                        if os.path.exists(downloaded_file):
                            filepath = downloaded_file
                except Exception as e:
                    print(f'ytdlp failed to download media from url: {url}, error: {e}')
        return filepath

    #main function body
    job_id = str(time.time()).replace('.', '')
    path, extension = os.path.splitext(os.path.basename(url))
    # include job_id in filename to avoid collisions when downloading concurrently
    if extension:
        filepath_name = f"{path}_{job_id}.{extension}"
    else:
        filepath_name = f"{escape_str(url)}_{job_id}"
    filepath = os.path.join(temp_dir, filepath_name)
    #ends with file extension
    parsed_uri = parse.urlparse(url)
    url_extension = parsed_uri.path.split('.')[-1]
    if (url_extension in image_extensions or url_extension in video_extensions):
        save_direct_media(url, job_id, filepath)
        #url is supported by ytdlp
    elif use_ytdlp:
        if any([netloc in parsed_uri.netloc for netloc in ytdlp_whitelist]):
            save_with_ytdlp(url, job_id, filepath)
    else:
        raise RuntimeError(f"unable to download file from url, no media found")
    
    #move file to queue
    database.move_file_to_queue(filepath, job_id)

def get_sub_urls_from_url(url: str) -> list:
    '''Extracts all linked URLs from the provided URL's page content.'''
    try:
        parsed_uri = parse.urlparse(url)
        response = get_and_check_response(url)
        if response is None:
            return []
        html = response.text
        html = re.sub(r'[\n]', ' ', html)  # remove new lines
        pattern = re.compile(r'(<a .*? href="(.*?)".*?>)')
        post_htmls = [x for x in re.findall(pattern, html)]

        post_sources = []
        for post in post_htmls:
            href = post[-1]
            if href == "" or href.startswith('#'):
                continue
            #check if url contains blacklisted keywords to avoid crawling unnecesary pages
            if any([(blacklisted in href) for blacklisted in blacklist]):
                if verbose:
                    pass
                    #print(f'skipping url due to blacklist: {href}')
                continue
            post_href = parse.urljoin(url, href)
            post_sources.append(post_href)

        filtered_child_urls = []
        if ignore_mirrors and parsed_uri.hostname in mirror_dict.keys():
            assert type(parsed_uri.hostname) == str
            ignore_list = mirror_dict[parsed_uri.hostname]
            for href in post_sources:
                href_netloc = parse.urlparse(href).netloc
                href_path = parse.urlparse(href).path

                #check if the url is from a mirror domain to avoid crawling the same page multiple times through different mirrors
                if (href_netloc not in ignore_list):
                    filtered_child_urls.append(href)
        else:
            filtered_child_urls = post_sources
        return filtered_child_urls
    except Exception as e:
        print(f'error checking url {url}: {e}')
        return []

def extract_media_urls_from_url(url: str, depth=0, recursive=False, depth_limit=depth_limit, ignore_blacklist=False, url_tree: urlTreeNode = None): # type: ignore
    '''given a url, extract media urls from it, if recursive is true, it will also extract urls from the pages and extract media from them up to the depth limit'''
    #check type of url
    if ignore_blacklist and url.split('.')[-1] in blacklist:
        return

    if verbose:
        print(f'{depth * "  "}extracting media from url: {url}, depth: {depth}, recursive: {recursive}')

    if url_tree:
        url_node = url_tree
    else:
        url_node = urlTreeNode(url)
    if is_media_url(url):
        # submit media download to background executor so crawling continues
        try:
            download_executor.submit(save_media_url, url, url_node.path_to_root())
        except Exception:
            # fallback to synchronous save if executor submission fails
            save_media_url(url, parent_sources=url_node.path_to_root())
            print(f"failed to submit media download for url: {url} to background executor, saved synchronously instead")
    else:
        #recurisve case, get sub urls and call function on them
        #uses a tree structure to keep track of urls and avoid duplicates
        sub_urls = get_sub_urls_from_url(url)
        #print(f'{depth * "  "}found {len(sub_urls)} sub urls from url: {url}')
        for child_url in sub_urls:
            #print(child_url not in url_node.get_all_urls())
            if recursive and depth < depth_limit and child_url not in url_node.get_all_urls():
                sub_url_tree = urlTreeNode(child_url, parent=url_node)
                extract_media_urls_from_url(child_url, depth+1, True, depth_limit, ignore_blacklist, url_tree=sub_url_tree)
    if depth == 0:
        #test media checker

        print(url_node.get_all_edges())
        print(f'finished extracting media from url: {url}, total urls found: {len(url_node.get_all_nodes())}, downloaded {len([node for node in url_node.get_all_nodes() if node.is_media])} media files')
        if verbose:
            print(f'all urls found: {url_node.get_all_urls()}')

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


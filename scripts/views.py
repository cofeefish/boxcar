from flask import render_template, redirect, url_for, Request, Response
import helpers, database, importer

def home(method, request_obj: Request):
    print('##################################################')
    t=database.quicktimer('time')
    query = request_obj.args.get('query', "")
    page = int(request_obj.args.get('page', 0))
    posts = database.filter_posts(query, page)

    tag_dict = helpers.tag_summary(posts)
    tag_dict = [(key, value) for key, value in tag_dict.items()][:20]
    time = t.finish()
    database.log_info("statisticts", {"event_type":"home_page_call","time":time,"query":query})
    
    return render_template("home.html", posts=posts, tag_dict=tag_dict, search=query)

####
def post(post_id):
    #get post obj
    post_obj = database.get_post(post_id)
    if post_obj == None:
        return redirect('/')
    elif type(post_obj) != helpers.post:
        raise TypeError(f'post_obj {post_obj} != helpers.post')
    #get image url
    media_url = url_for('media', filename=post_obj.filepath)
    return render_template("post.html", post=post_obj, media_url=media_url)

def create_post(method, request_obj: Request, job_id):
    #edit page for creating post from queue item
    args = request_obj.args
    path = args.get('path')
    assert type(path) == str
    time = args.get('time')
    source = args.get('source', type=str)
    assert type(source) == str
    source=source.strip("'")
    source_list=source.split(importer.source_splitter_str)

    t=database.quicktimer("get tags")
    tags = importer.get_tags_from_many_url(source_list)
    t.finish()

    t=database.quicktimer("thumbnail")
    thumbnail = helpers.make_thumbnaill(path.strip("'"), size=(1024,1024), to_link=True)
    t.finish()

    media = helpers.get_media_attributes(path.strip("'"))
    return render_template('create_post.html',source=source, thumbnail=thumbnail, filepath=path, job_id=job_id, tags=tags, media=media)

def finalize_post(method, request_obj: Request):
    form = request_obj.form 
    t=database.quicktimer("make post obj")
    post_obj = helpers.post(
        job_id = form.get('job_id', 'off'),
        post_id = database.get_next_id(),
        is_hidden = form.get('is_hidden', 'off') == 'on',
        parent_id = form.get('parent-id', ''),
        children = form.get('children', []),
        score = int(form.get('score-input', 0)),
        fav = form.get('fav-input', 'off') == 'on',
        views = int(form.get('views-input', 0)),
        sources = form.get('sources-input',"").split(importer.source_splitter_str),
        rating = form.get('rating-input', ''),
        tag_string = form.get('tags-input', ''),
        title = form.get('title-input', ''),
        description= form.get('description-input', ''),
        filepath = form.get('filepath-input', '')
    )
    t.finish()
    t=database.quicktimer("save post")
    post_obj.save()
    t.finish()
    return redirect('posts/' + str(post_obj.id))

def edit_post(post_id, request_obj: Request):
    post_obj = database.get_post(post_id)
    assert post_obj != None

    form = request_obj.form.to_dict()
    print(form)
    #return
    post_obj.is_hidden = form.get('is_hidden', 'off') == 'on'
    post_obj.parent_id = form.get('parent-id', '')
    post_obj.children = list(form.get('children', "").split(" "))
    post_obj.score = int(form.get('score-input', 0))
    post_obj.fav = form.get('fav-input', 'off') == 'on'
    post_obj.views = int(form.get('views-input', 0))
    post_obj.sources = form.get('sources-input',"").split(" ")
    post_obj.rating = form.get('rating-input', '')
    post_obj.tag_string = form.get('tags-input', '')
    post_obj.title = form.get('title-input', '')
    post_obj.description = form.get('description-input', '')

    void, post_trim_in, post_trim_out = form.get('marker_times', '').split(', ')
    import video_editor
    video_editor.crop_trim(post_obj.filepath, post_obj.filepath, 0, 0, -1, -1, float(post_trim_in), float(post_trim_out))

    post_obj.save()
    media_url = url_for('media', filename=post_obj.filepath)
    return render_template("post.html", post=post_obj, media_url=media_url)

def delete_post(post_id):
    post_obj = database.get_post(post_id)
    assert post_obj != None

    post_obj.delete()
    return str(True)

####
def queue():
    t=database.quicktimer("get queue")
    queue = helpers.get_queue()
    t.finish()
    t=database.quicktimer("everything else")
    ongoing_uploads = queue["ongoing"]
    assert type(ongoing_uploads) == list
    recent_items = queue["completed"][-10:][::-1] + queue["errors"][-10:][::-1]
    t.finish()
    return render_template("queue.html", ongoing = ongoing_uploads, recent_items = recent_items)

def delete_queueitem(method, request_obj: Request):
    request_dict = request_obj.json
    assert type(request_dict) == dict
    job_id = request_dict['job_id']
    helpers.delete_queueitem(job_id)
    if job_id != None:
        return str(True)
    return str(False)

def upload(method, request_obj: Request):
    if method == "GET":
        return render_template("upload_start.html")
    elif method == "POST":
        #process upload
        source_dir = database.get_source_dir()

        all_files = request_obj.files.getlist('upload[files][]')
        request_dict = dict(request_obj.form.to_dict(flat=False))
        url = request_dict.get('upload[source]', [""])[0]
        
        if (url != ""):
            filepath=database.temp_dir
            url_list = url.split(' ')
            for url in url_list:
                importer.save_media_from_url(filepath, sources = [url])
        else:
            for file in all_files:
                #print(f"Uploading file: {file.filename}")
                database.add_file_to_queue(file)

        return redirect("/queue")
    return redirect("/")
from flask import Flask, request, abort
import os
import views, helpers, database

source_dir = database.get_source_dir()
app = Flask(__name__, static_folder=f'{source_dir}\\static', template_folder=f'{source_dir}\\templates')

###########################################

@app.route('/media/<path:filename>')
def media(filename:str):
    from flask import send_file
    if not os.path.exists(filename):
        print(f'while viewing media, {filename} : does not exist')
        abort(404)
    filename = os.path.normpath(filename)
    #print(filename)
    return send_file(filename)

@app.route('/delete_queueitem', methods=['POST'])
def delete_queueitem(): return views.delete_queueitem(request.method, request)
#

@app.route('/')
def home():      return views.home(request.method, request)

@app.route('/create_post/<filepath>')
def post_creation(filepath): return views.create_post(request.method, request, filepath)

@app.route('/delete_post/<post>', methods=["POST"])
def delete_post(post): return views.delete_post(post)

@app.route('/finalize_post', methods=["POST"])
def post_finaliazation(): return views.finalize_post(request.method, request)

@app.route('/posts/<post_name>')
def post_page(post_name):   return views.post(post_name)

@app.route('/edit_post/<post_name>', methods=["POST"])
def edit_post(post_name):   return views.edit_post(post_name, request)

@app.route('/queue')
def queue():     return views.queue()

@app.route('/upload', methods=['GET', "POST"])
def upload():    return views.upload(request.method, request)

############################################

if __name__ == '__main__':
    import socket
    helpers.initialize()
    port = 1741
    #host = '127.0.0.1' #available to this computer
    host = '0.0.0.0' #available to whole network

    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    print(f'Server started on {hostname} at {ip_address}:{port}')
    app.run(debug=True, host=host, port=port)
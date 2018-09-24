import flask
from flask import request, jsonify, render_template, json, abort, Response, flash, g, current_app, make_response
from flask_basicauth import BasicAuth
from flask.cli import AppGroup
import click
import sqlite3

app = flask.Flask(__name__)
app.config['DEBUG'] = True

class Authentication(BasicAuth):
    def check_credentials(self, username, password):
        print('check_credentials')
        # query from database 
        query = "SELECT * from users where username ='{}'".format(username)
        user = query_db(query)
        if user == []:
            return False
        if user[0]['password'] == password:
            current_app.config['BASIC_AUTH_USERNAME'] = username
            current_app.config['BASIC_AUTH_PASSWORD'] = password
            return True
        else: 
            return False
       

basic_auth = Authentication(app)
DATABASE = './init.db'

#Function Connect Database
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db
    
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

#Function  execute script
def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('init.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

#Create Command initdb
#To use command, run in terminal export FLASK_APP = appname, flask initdb
@app.cli.command('init_db')
def initdb_command():
    init_db()
    print('Initialize the database.')        

#
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d
    
#Function using for query database
#Fetch each data one by one based on the query provided
def query_db(query, args=(), one=False):
    conn = get_db()
    conn.row_factory = dict_factory
    cur = conn. cursor()
    fetch = cur.execute(query).fetchall()
    return fetch
    
    
#Notify error with status code, response and reason
def notify_error(status_code, response, reason):
    notify = jsonify({
    "status" : status_code,
    "response": response,
    "reason": reason
    })
    return notify
          
#Create User
@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json(force=True)
    username = data['username']
    password = data['password']


    query = 'SELECT username FROM users'
    listusername = query_db(query)
    for user_name in listusername:
        if user_name['username'] == username:
            return notify_error(409, 'Conflict', 'Username already exists')

    db = get_db()
    db.execute('insert into users(username, password) values (?,?)', (username,password))
    db.commit()

    response = make_response('Success: account created')
    response.status_code = 201
    return response

#Still working on it.
#Change User Password
@app.route('/users/<string:user>', methods=['PUT'])
# @basic_auth.required
def change_password(user):
    data = request.get_json(force=True)
    newpassword = data['password']
    # creator = current_app.config['BASIC_AUTH_USERNAME']

    query = "SELECT Id FROM USERS WHERE username = '{}'".format(str(user))
    useracc = query_db(query)
    if not useracc:
        error = '404 No user exists with the user of ' + str(user)
        return make_response(jsonify({'error': error}), 404)
    db = get_db()
    db.execute("UPDATE users SET password= ? WHERE username= ?",(newpassword, str(user)))
    db.commit()
    response = make_response("Success: User password Changed ")
    response.status_code = 201
    return response

#List available discussion forums
@app.route('/forums', methods = ['GET'])
def api_forums():
    query = "SELECT * FROM forums;"
    forums = query_db(query)

    # all_forums = query_db('SELECT forums.Id, forums.forum_name, user.username FROM  forums INNER JOIN user ON forums.Id = user.Id ;')
    return jsonify(forums)

#List threads in the specified forum
@app.route('/forums/<int:forum_id>', methods = ['GET'])
def api_threads(forum_id):
    query = 'SELECT Id FROM forums WHERE Id = ' + str(forum_id) +';'
    forum = query_db(query)
    if not forum :
        return notify_error(404, 'Error', 'No forum exists with the the forum id of ' + str(forum_id))   
    else:
        # query = 'SELECT threads.Id, threads.thread_title, threads.thread_time, user.username as creator FROM user, threads  where  forum_Id = ' + str(forum_id) +' AND threads.thread_creator = user.Id ORDER BY thread_time DESC;'
        query = 'SELECT * FROM forums WHERE id = ' + str(forum_id)
        threads = query_db(query)
        return jsonify(threads)
        
#List posts in the specified thread
@app.route('/forums/<int:forum_id>/<int:thread_id>', methods=['GET'])
def get_post(forum_id, thread_id):
    print(forum_id, thread_id)
     # Select from forums on forum id to make sure that the forum exists
    query = 'SELECT * FROM forums WHERE id = ' + str(forum_id)
    forum = query_db(query)
    if not forum:
        return notify_error(404, 'Error', 'No forum exists with the the forum id of ' + str(forum_id))   
    # Select from threads on thread_id to make sure thread exists
    query = 'SELECT * FROM threads WHERE id = ' + str(thread_id)
    thread = query_db(query)
    if not thread:
        return notify_error(404, 'Error', 'No thread exists with the the thread id of ' + str(thread_id))   
    query = "SELECT * FROM posts WHERE post_threadId = {} AND post_forumid = {}".format(str(thread_id), str(forum_id))
    post = query_db(query)
    return jsonify(post)

#POST FORUM
@app.route('/forums', methods=['POST'])
@basic_auth.required
def post_forums():

    data = request.get_json(force=True)
    name = data['forum_name']

    creator = current_app.config['BASIC_AUTH_USERNAME']
    query = 'SELECT forum_name FROM forums'
    forum_names = query_db(query)
    for forum_name in forum_names:
        if forum_name['forum_name'] == name:
            error = '409 A forum already exists with the name ' + name
            return make_response(jsonify({'error': error}), 409)
   
    db = get_db()
    db.execute('insert into forums (forum_name, forum_creator) values (?, ?)',(name, creator))
    db.commit()

    query = "select Id from forums where forum_name ='{}'".format(name)
    new_forum = query_db(query)
    response = make_response('Success: forum created')
    response.headers['location'] = '/forums/{}'.format(new_forum[0]['Id'])
    response.status_code = 201

    return response

#POST THREAD
@app.route('/forums/<int:forum_id>', methods=['POST'])
@basic_auth.required
def post_thread(forum_id):

    data = request.get_json(force=True)
    title = data['thread_title']
    text = data['text']
    creator = current_app.config['BASIC_AUTH_USERNAME']

     # Select from forums on forum id to make sure that the forum exists
    query = 'SELECT * FROM forums WHERE id = ' + str(forum_id)
    forum = query_db(query)
    print(forum)
    if len(forum) == 0:
        error = '404 No forum exists with the forum id of ' + str(forum_id)
        return make_response(jsonify({'error': error}), 404)
    # If forum exist, insert into threads table
    db = get_db()
    db.execute('insert into threads (thread_title, thread_creator, forum_Id) values (?, ?, ?)',(title, creator, str(forum_id)))
    db.commit()
    # Get the thread_id from the new thread to put into post's thread_id
    file_entry = query_db('SELECT last_insert_rowid()')
    thread_id = file_entry[0]['last_insert_rowid()']
    # Insert text as a new post
    db.execute('insert into posts (post_text, post_authorid , post_threadId, post_forumid) values (?, ?, ?, ?)',(text, creator, str(thread_id), str(forum_id)))
    db.commit()

    response = make_response("Success: Thread and Post created")
    response.headers['location'] = '/forums/{}/{}'.format(str(forum_id), thread_id)
    response.status_code = 201
    return response

#POST POST
@app.route('/forums/<int:forum_id>/<int:thread_id>', methods=['POST'])
@basic_auth.required
def post_post(forum_id, thread_id):
    # Select from forums on forum id to make sure that the forum exists
    query = 'SELECT * FROM forums WHERE id = ' + str(forum_id)
    forum = query_db(query)
    print(forum)
    if len(forum) == 0:
        error = '404 No forum exists with the forum id of ' + str(forum_id)
        return make_response(jsonify({'error': error}), 404)
    # Select from threads on thread_id to make sure thread exists
    query = 'SELECT * FROM threads WHERE id = ' + str(thread_id)
    thread = query_db(query)
    print(thread)
    if len(thread) == 0:
        error = '404 No thread exists with the thread id of ' + str(thread_id)
        return make_response(jsonify({'error': error}), 404)
    
    data = request.get_json(force=True)
    creator = current_app.config['BASIC_AUTH_USERNAME']
    text = data['text']

    # Insert text as a new post
    db = get_db()
    db.execute('insert into posts (post_text, post_authorid , post_threadId, post_forumid) values (?, ?, ?, ?)',(text, creator, str(thread_id), str(forum_id)))
    db.commit()

    response = make_response("Success: Post created")
    response.headers['location'] = '/forums/{}/{}'.format(str(forum_id), thread_id)
    response.status_code = 201
    return response

    
if __name__ == "__main__":
    app.run(debug=True)
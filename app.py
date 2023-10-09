import json
from flask import Flask, jsonify, request, render_template, redirect, session, url_for
from flask_sse import sse
from flask_socketio import SocketIO, emit
from flask_mysqldb import MySQL
from flask_cors import CORS
from urllib.parse import unquote
import MySQLdb.cursors
import secrets
import requests
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import gspread
import re

FB_GRAPH_BASE_URL = 'https://graph.facebook.com/v17.0'
PAGE_ID = '114887508325720'
INSTA_ID = '17841405286734922'
PAGE_ACCESS_TOKEN = 'EAAJLYZCAAqKwBAFpDeAsxqKGZCB9Gmirqpzr0tcDOJGlQ1G951V6wTk904kISIcvekZBmAqwso9KycRpQuxn1lznnjZB8myHLIZBqPJbXyXOn8b0DYjZB3Mgp9p6MK6TEZAmOgvYUykearZBo5FqZCo9a8ubZAuGnJwwJdj6xZALgoGsYHUYFaRpRm6'
# PAGE_ACCESS_TOKEN_INSTA = 'EAAJLYZCAAqKwBAAAm4iAGdGQx1GD2WZBmdMlpj82uQEbZBXElLPZB86Wgl9UjzO8ckqzxQXyeZBX4Ta6An8hL5c36HOo0ZCrSjbtW1V4Ur0FGRZBRWmK0HuSsnge4A81v9ANaHDuF9IiLfPZBVY8GXDe3GxqZB92y5vfPxJoZA58tM3ySd7dqmO7iV'

app = Flask(__name__)

# CORS(app, resources={r"/*": {"origins": "*"}})

app.secret_key = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'crm'

mysql = MySQL(app)

def process_conversations(data):
    conversations = {}
    for conversation in data:
        participants = conversation['participants']['data']
        messages = []
        for message in conversation['messages']['data']:
            attachments = []
            if 'attachments' in message:
                for attachment in message['attachments']['data']:
                    name = attachment['name']
                    size = attachment['size']
                    if 'image' in attachment['mime_type']:
                        # attachment_type = 'image_data'
                        attachments.append({
                            'type': attachment['mime_type'],
                            'name': name,
                            'size': size,
                            'url': attachment['image_data']['preview_url']
                        })
                    elif 'video' in attachment['mime_type']:
                        # attachment_type = 'video_data'
                        attachments.append({
                            'type': attachment['mime_type'],
                            'name': name,
                            'size': size,
                            'url': attachment['video_data']['url']
                        })
                    elif 'application' in attachment['mime_type']:
                        attachments.append({
                            'type': attachment['mime_type'],
                            'name': name,
                            'size': size,
                            'url': attachment['file_url']
                        })
            messages.append({
                'message_id': message['id'],
                'message': message['message'],
                'timestamp': message['created_time'],
                'from': message['from']['id'],
                'to': message['to']['data'][0]['id'],
                'attachments': attachments
            })
        if participants:
            participant = participants[0]
            # print(participant)
            id = participant['id']
            if 'name' in participant:
                name = participants[0]['name']
            elif 'username' in participant:
                name = participants[1]['username']
            else:
                name = ''
            conversation_dict = {
                'id': id,
                'name': name,
                'messages': messages,
                'read_timestamp': messages[0]['timestamp']
            }
            conversations[conversation['id']] = conversation_dict

    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM message_reads')
    data = cursor.fetchall()
    # print(data)
    for x in data:
        if conversations.get(x['id']) != None:
            # print('fayez')
            conversations[x['id']]['read_timestamp'] = x['timestamp']

    return conversations

def sort_conversations(conversation_id, platform):
    global sorted_conversations, messenger_conversations, instagram_conversations
    # sorted_conversations = dict(sorted(sorted_conversations.items(), key=lambda x: x[1]['messages'][0]['timestamp'], reverse=True))
    tmp = sorted_conversations[conversation_id]
    del sorted_conversations[conversation_id]
    sorted_conversations = {conversation_id: tmp, **sorted_conversations}

    if platform == 'fb':
        if messenger_conversations.get(conversation_id) != None:
            del messenger_conversations[conversation_id]
        messenger_conversations = {conversation_id: tmp, **messenger_conversations}
    elif platform == 'insta':
        if instagram_conversations.get(conversation_id) != None:
            del instagram_conversations[conversation_id]
        instagram_conversations = {conversation_id: tmp, **instagram_conversations}


def getConversationDict(page_id, page_access_token, platform = None):
    conversations_params = {
        'fields': 'participants,messages{id,message,created_time,from,to,attachments}',
        'access_token': page_access_token,
    }

    # Retrieve conversations from Instagram
    instagram_params = conversations_params.copy()
    instagram_params['platform'] = 'instagram'

    instagram_conversations = requests.get(
        f'{FB_GRAPH_BASE_URL}/me/conversations',
        params=instagram_params
    )
    # print(instagram_conversations.json())
    try:
        instagram_data = instagram_conversations.json()['data']
    except:
        instagram_data = []
    instagram_conversations = process_conversations(instagram_data)
    # return instagram_conversations
    
    # elif platform == 'fb':
    # Retrieve conversations from Messenger
    messenger_params = conversations_params.copy()

    messenger_conversations = requests.get(
        f'{FB_GRAPH_BASE_URL}/{page_id}/conversations',
        params=messenger_params
    )
    # print(messenger_conversations.json())
    messenger_data = messenger_conversations.json()['data']
    messenger_conversations = process_conversations(messenger_data)
    # return messenger_conversations

    if platform == 'insta':
        return messenger_conversations
    elif platform == 'fb':
        return messenger_conversations
    else:
        # Merge conversations and sort by timestamp in descending order
        all_conversations = {}
        for id,conversation in instagram_conversations.items():
            all_conversations[id] = conversation

        for id,conversation in messenger_conversations.items():
            all_conversations[id] = conversation

        sorted_conversations = dict(sorted(all_conversations.items(), key=lambda x: x[1]['messages'][0]['timestamp'], reverse=True))
        return messenger_conversations

sorted_conversations = {}
messenger_conversations = {}
instagram_conversations = {}
message_received = {}

@app.route('/')
def index():
	# if not session:
	# 	session['loggedin'] = False
	if not session or not session['loggedin']:
		return redirect(url_for('login'))
	else:
		return render_template('index.html', username=session['username'], role=session['role'])

@app.route("/login", methods=["GET", "POST"])
def login():
    if not session or not session['loggedin']:
        msg = ''
        if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'role' in request.form:
            username = request.form['username']
            password = request.form['password']
            # role = '1'
            role = request.form['role']
            # print(role)
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute('SELECT * FROM employees WHERE username = %s AND password = %s AND role_id = %s', (username, password, role))
            account = cursor.fetchone()
            if account:
                session['loggedin'] = True
                session['id'] = account['id']
                session['username'] = account['username']
                session['role'] = account['role_id']
                # session['name'] = account['name']
                msg = 'Logged in successfully !'
                return redirect(url_for('index'))
            else:
                msg = 'Incorrect username / password !'
        return render_template('login.html', msg=msg)
    else:
        return redirect(url_for('index'))
    
@app.route('/logout', methods=['POST'])
def logout():
    session['loggedin'] = False
    session.pop('id', None)
    session.pop('email', None)
    session.pop('name', None)
    return redirect(url_for('login'))

@app.route('/chat/<page_id>', methods=['GET'])
def chat(page_id):
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    else:
        # pages = []
        # if session['role'] == 2:
        # cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # cursor.execute('SELECT * FROM pages WHERE id IN (SELECT page_id FROM employee_pages WHERE employee_id = %s)', (session['id'],))
        # pages = cursor.fetchall()
        # print(pages)
        # for x in data:
        #     pages.append(x['page_id'])

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT name, access_token FROM pages WHERE id = %s', (page_id,))
        data = cursor.fetchone()
        # print(data)
        access_token = data['access_token']
        page_name = data['name']
    
        return render_template('chat.html', username=session['username'], role=session['role'], page_id=page_id, page_name=page_name, access_token=access_token)
    
@app.route('/privacy', methods=['GET'])
def privacy():
    return render_template('privacy.html')

@app.route('/getPages', methods=['GET'])
def getPages():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM pages WHERE id IN (SELECT page_id FROM employee_pages WHERE employee_id = %s)', (session['id'],))
    data = cursor.fetchall()
    # for row in data:
    #     row['url'] = r"{{ url_for('chat', page_id=' + row['id'] + ') }}"
    # print(data)
    return jsonify(data)
    
@app.route('/getIds', methods=['GET'])
def getIds():
    return {'page_id': PAGE_ID, 'insta_id': INSTA_ID}

@app.route('/getConversations/<page_id>/<page_access_token>/<platform>', methods=['GET'])
def getConversations(page_id, page_access_token, platform):
    # print(session['role'])
    global sorted_conversations, messenger_conversations, instagram_conversations
    global PAGE_ID, PAGE_ACCESS_TOKEN
    PAGE_ID = page_id
    PAGE_ACCESS_TOKEN = page_access_token
    if session['role'] == 1:
        if platform == 'fb':
            messenger_conversations = getConversationDict(page_id, page_access_token, platform)
            return [{'id': conv_id, 'name': details['name'], 'last_message': details['messages'][0]['message'], 'sender': details['messages'][0]['from'], 'timestamp': details['messages'][0]['timestamp'], 'read_timestamp': details['read_timestamp']} for conv_id,details in messenger_conversations.items()]
        elif platform == 'insta':
            instagram_conversations = getConversationDict(page_id, page_access_token, platform)
            return [{'id': conv_id, 'name': details['name'], 'last_message': details['messages'][0]['message'], 'sender': details['messages'][0]['from'], 'timestamp': details['messages'][0]['timestamp'], 'read_timestamp': details['read_timestamp']} for conv_id,details in instagram_conversations.items()]
        elif platform == 'all':
            sorted_conversations = getConversationDict(page_id, page_access_token)
            return [{'id': conv_id, 'name': details['name'], 'last_message': details['messages'][0]['message'], 'sender': details['messages'][0]['from'], 'timestamp': details['messages'][0]['timestamp'], 'read_timestamp': details['read_timestamp']} for conv_id,details in sorted_conversations.items()]
    elif session['role'] == 2:
        # print(page_access_token)
        # print(PAGE_ACCESS_TOKEN)
        sorted_conversations = getConversationDict(page_id, page_access_token)
        # print(conversations)
        return [{'id': conv_id, 'name': details['name'], 'last_message': details['messages'][0]['message'], 'sender': details['messages'][0]['from'], 'timestamp': details['messages'][0]['timestamp'], 'read_timestamp': details['read_timestamp']} for conv_id,details in sorted_conversations.items()]
    elif session['role'] > 2:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT conversation_id FROM chat_shares WHERE receiver_id = %s', (session['id'],))
        data = cursor.fetchall()
        # print(data)
        convs = []
        for x in data:
            convs.append({'id': x['conversation_id'], 'name': sorted_conversations[x['conversation_id']]['name'], 'last_message': sorted_conversations[x['conversation_id']]['messages'][0]['message'], 'sender': sorted_conversations[x['conversation_id']]['messages'][0]['from'], 'timestamp': sorted_conversations[x['conversation_id']]['messages'][0]['timestamp'], 'read_timestamp': sorted_conversations[x['conversation_id']]['read_timestamp']})
        # return [{'id': conv_id, 'name': details['name']} for conv_id,details in conversations.items()]
        return convs
    
@app.route('/getMessages/<conversation_id>', methods=['GET'])
def getMessages(conversation_id):
    # conversations = sorted_conversations
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT timestamp FROM message_reads WHERE id = %s', (conversation_id,))
    data = cursor.fetchone()

    if data and data['timestamp'] != sorted_conversations[conversation_id]['messages'][0]['timestamp']:
        cursor.execute('UPDATE message_reads SET timestamp = %s where id = %s', (sorted_conversations[conversation_id]['messages'][0]['timestamp'],conversation_id))
    elif data == None:
        cursor.execute('INSERT INTO message_reads (id, timestamp) VALUES (%s, %s)', (conversation_id, sorted_conversations[conversation_id]['messages'][0]['timestamp']))
    mysql.connection.commit()

    sorted_conversations[conversation_id]['read_timestamp'] = sorted_conversations[conversation_id]['messages'][0]['timestamp'] 

    if session['role'] > 2:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT timestamp FROM chat_shares WHERE receiver_id = %s AND conversation_id = %s', (session['id'], conversation_id))
        data = cursor.fetchone()
        # print(data)
        timestamp = data['timestamp'] if data != None else ''
        print(timestamp)
        messages = []

        for message in sorted_conversations[conversation_id]['messages']:
            # print(message['timestamp'], timestamp)
            if message['timestamp'] > timestamp:
                messages.append(message)

        return [{"id": sorted_conversations[conversation_id]['id'], "name": sorted_conversations[conversation_id]['name']}, messages]
    else:
        # print( conversations[conversation_id])
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # print(sorted_conversations)
        cursor.execute('SELECT * FROM contacts WHERE id = %s', (sorted_conversations[conversation_id]['id'],))
        data = cursor.fetchone()
        return [{"id": sorted_conversations[conversation_id]['id'], "name": sorted_conversations[conversation_id]['name']}, sorted_conversations[conversation_id]['messages'], data]

@app.route("/checkMessage", methods=["GET", "POST"])
def check_message():
    global message_received
    if message_received:
        tmp = message_received
        message_received = {}
        print('fayez')
        print(tmp)
        return jsonify(tmp)
    return 'no message received'

@app.route("/receiveMessage", methods=["GET", "POST"])
def receive_message():
    # print(request.get_json())
    # return 'success',200

    # hub_challenge = request.args.get("hub.challenge")
    # return hub_challenge, 200

    post_data = request.get_json()
    print(post_data)
    sender_id = post_data['entry'][0]['messaging'][0]['sender']['id']
    message_id = message = post_data['entry'][0]['messaging'][0]['message']['mid']
    message = post_data['entry'][0]['messaging'][0]['message']['text'] if 'text' in post_data['entry'][0]['messaging'][0]['message'] else ''
    # _from = post_data['entry'][0]['messaging'][0]['message']['from']['id']
    receiver_id = post_data['entry'][0]['id']
    # print(receiver_id)
    if post_data['object'] == 'page':
        p = 'messenger'
        platform = 'fb'
    elif post_data['object'] == 'instagram':
        p = 'instagram'
        platform = 'insta'
    # sender_name = post_data['entry'][0]['messaging'][0]['sender']['name']
    # sender_name = ''

    # attachment_type = response.json()['data'][0]['mime_type']
    # name = response.json()['data'][0]['name']
    # size = response.json()['data'][0]['size']

    # if attachment_type == 'image' or attachment_type == 'video':
    #     url = response.json()['data'][0][f'{attachment_type}_data']['preview_url']
    # else:
    #     url = response.json()['data'][0]['file_url']

    attachment = []
    # index = 0
    # if 'attachments' in post_data['entry'][0]['messaging'][0]['message']:
    #     for x in post_data['entry'][0]['messaging'][0]['message']['attachments']:
    #         # print(post_data['entry'][0]['messaging'])
    #         if x['type'] == 'file':
    #             response = requests.get(f'{FB_GRAPH_BASE_URL}/{message_id}/attachments', params={'access_token': PAGE_ACCESS_TOKEN})
    #             attachment_type = response.json()['data'][index]['mime_type']
    #             name = response.json()['data'][index]['name']
    #             size = response.json()['data'][index]['size']
    #             url = response.json()['data'][index]['file_url']
    #             attachment.append({'type': attachment_type, 'name': name, 'size': size, 'url': url})
    #         else:
    #             attachment.append({'type': x['type'], 'name': '', 'size': '', 'url': x['payload']['url']})
    #     index += 1

    response = requests.get(f'{FB_GRAPH_BASE_URL}/{message_id}/attachments', params={'access_token': PAGE_ACCESS_TOKEN})
    
    try:
        for x in response.json()['data']:
            if 'image' in x['mime_type']:
                attachment_type = 'image'
            elif 'video' in x['mime_type']:
                attachment_type = 'video'
            else:
                attachment_type = 'file'

            if attachment_type == 'image' or attachment_type == 'video':
                url = x[f'{attachment_type}_data']['preview_url']
            else:
                url = x['file_url']

            attachment.append({'type': x['mime_type'], 'name': x['name'], 'size': x['size'], 'url': url})
    except:
        attachment = []

    # attachment = post_data['entry'][0]['messaging'][0]['message']['attachments'][0] if 'attachments' in post_data['entry'][0]['messaging'][0]['message'] else []
    # print(sender_id, receiver_id, message, attachment)
    # print(sender_id, receiver_id)
    conversations_params = {
        'fields': 'participants',
        'user_id': sender_id,
        'platform': p,
        'access_token': PAGE_ACCESS_TOKEN,
    }

    response = requests.get(
        f"{FB_GRAPH_BASE_URL}/{PAGE_ID}/conversations",
        params=conversations_params
    )
    print(response.json())
    conversation_id = response.json()['data'][0]['id']
    # print(conversation_id)
    if p == 'messenger':
        sender_name = response.json()['data'][0]['participants']['data'][0]['name']
    else:
        sender_name = response.json()['data'][0]['participants']['data'][1]['username']
        # print(sender_name)
    # print(conversation_id)

    # global sorted_conversations

    timestamp = datetime.utcnow()
    timestamp_plus_one_second = timestamp + timedelta(seconds=1)
    timestamp = timestamp_plus_one_second.strftime('%Y-%m-%dT%H:%M:%S+0000')

    if sorted_conversations.get(conversation_id) != None:
        sorted_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment})
    else:
        # sorted_conversations = {}
        sorted_conversations[conversation_id] = {'id': sender_id, 'name': sender_name, 'messages': [{'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment}]}
        # tmp = sorted_conversations[conversation_id]
        # del sorted_conversations[conversation_id]
        # sorted_conversations = {conversation_id: tmp, **sorted_conversations}

        # tmp = {}
        # tmp[conversation_id] = sorted_conversations[conversation_id]
        # for key, value in sorted_conversations.items():
        #     if key != conversation_id:
        #         tmp[key] = value
        # sorted_conversations = tmp

    # tmp = conversations.pop(conversation_id)
    # print(tmp)
    # conversations.update({conversation_id: tmp})
    # print(conversations)

    sort_conversations(conversation_id, platform)
    
    # socketio.emit('message_received', {'data': {'id': sender_id, 'name': sender_name, 'messages': [{'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment}]}})
    global message_received
    message_received = {'data': {'conversation_id': conversation_id, 'id': sender_id, 'name': sender_name, 'messages': [{'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment}]}}

    return timestamp

@app.route("/sendMessage", methods=["POST"])
def send_message():
    message = request.form['message']
    recipient_id = request.form['recipient_id']
    platform = request.form['platform']
    
    message_params = {
        'recipient': json.dumps({'id': recipient_id}),
        'message': json.dumps({
            'text': message,
        }),
        'messaging_type': 'RESPONSE',
        'access_token': PAGE_ACCESS_TOKEN,
    }

    response = requests.post(
        f"{FB_GRAPH_BASE_URL}/{PAGE_ID}/messages",
        params=message_params
    )

    timestamp = datetime.utcnow()
    timestamp_plus_one_second = timestamp + timedelta(seconds=1)
    timestamp = timestamp_plus_one_second.strftime('%Y-%m-%dT%H:%M:%S+0000')
    # print('Time Sent: ', timestamp)
    print(response.json())
    message_id = response.json()['message_id']

    # response = requests.get(f'https://graph.facebook.com/v13.0/{message_id}',
    #                     params={'access_token': PAGE_ACCESS_TOKEN})
    # data = response.json()
    # timestamp = data['created_time']
    # print('Time Sent: ', timestamp)

    # print(response.json())
    for conversation_id, conversation in sorted_conversations.items():
        # print(key, value)
        if conversation['messages'][0]['from'] == recipient_id:
            conversation_id = conversation_id
            break
        elif conversation['messages'][0]['to'] == recipient_id:
            conversation_id = conversation_id
            break

    # conversation_id = ''
    # print(conversation_id)
    
    sorted_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': []})
    
    # if platform == 'fb':
    #     messenger_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': []})
    # elif platform == 'insta':
    #     instagram_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': []})

    # global sorted_conversations
    # if sorted_conversations.get(conversation_id) != None:
    #     sorted_conversations[conversation_id]['messages'].insert(0, {'message': message, 'from': sender_id, 'to': receiver_id, 'attachments': attachment})

    sort_conversations(conversation_id, platform)

    return timestamp

@app.route("/sendAttachment", methods=["POST"])
def send_attachment():
    url = "https://graph.facebook.com/v17.0/me/message_attachments"

    recipient_id = request.form['recipient_id']
    file = request.files['file']
    platform = request.form['platform']
    # print(file.filename)
    # access_token = "<PAGE_ACCESS_TOKEN>"
    # file_path = r"C:\Users\USER\Desktop\example.png"

    allowed_image_extensions = ('png', 'jpg', 'jpeg', 'gif')
    allowed_video_extensions = ('mp4', 'avi', 'mov')
    allowed_zip_extensions = ('zip', 'rar')
    
    file_extension = file.filename.lower().split('.')[-1]
    print(file_extension)
    if file_extension in allowed_image_extensions:
        attachment_type = "image"
        file_mime_type = "image/png"  # Update with appropriate image mime type
    elif file_extension in allowed_video_extensions:
        attachment_type = "video"
        file_mime_type = "video/mp4"  # Update with appropriate video mime type
    elif file_extension in allowed_zip_extensions:
        attachment_type = "file"
        file_mime_type = "application/zip"  # Update with appropriate zip mime type
    else:
        return "Unsupported file type"
    
    message = {
        "attachment": {
            "type": attachment_type,
            "payload": {
                "is_reusable": True
            }
        }
    }

    # with open(file_path, "rb") as file:
    #     files = {
    #         "filedata": (file.name, file.read(), "image/png")
    #     }

    files = {
        "filedata": (file.filename, file.stream.read(), file_mime_type)
    }

    params = {
        "access_token": PAGE_ACCESS_TOKEN
    }

    response = requests.post(url, params=params, files=files, data={"message": json.dumps(message)})
    # print(response.json())
    try:
        attachment_id = response.json()['attachment_id']
    except:
         return response.json()
    
    # image_url = f"https://www.facebook.com/{recipient_id}/attachments/{attachment_id}/"

    # Retrieve image URL using attachment_id
    # image_url_url = f"https://graph.facebook.com/v17.0/{attachment_id}"
    # image_url_params = {
    #     "fields": "url",
    #     "access_token": PAGE_ACCESS_TOKEN
    # }

    # image_url_response = requests.get(image_url_url, params=image_url_params)

    # if image_url_response.status_code == 200:
    #     print(image_url)
    # else:
    #     print("Failed to retrieve image URL.")

    # print(image_url_response.json())

    message_params = {
        'recipient': json.dumps({'id': recipient_id}),
        'message': json.dumps({
            "attachment":{
                "type": attachment_type, 
                "payload":{
                    "attachment_id": attachment_id
                }
            }
        }),
        'messaging_type': 'RESPONSE',
        'access_token': PAGE_ACCESS_TOKEN,
    }

    response = requests.post(
        f"{FB_GRAPH_BASE_URL}/{PAGE_ID}/messages",
        params=message_params
    )

    timestamp = datetime.utcnow()
    timestamp_plus_one_second = timestamp + timedelta(seconds=1)
    timestamp = timestamp_plus_one_second.strftime('%Y-%m-%dT%H:%M:%S+0000')

    # print(response.json())

    message_id = response.json()['message_id']

    params = {
        # 'fields': 'image_data',
        'access_token': PAGE_ACCESS_TOKEN,
    }

    response = requests.get(f'{FB_GRAPH_BASE_URL}/{message_id}/attachments', params=params)
    print(response.json())
    # print(file.content_length)
    if attachment_type == 'image' or attachment_type == 'video':
        url = response.json()['data'][0][f'{attachment_type}_data']['preview_url']
    else:
        url = response.json()['data'][0]['file_url']
    # print(image_url)

    name = response.json()['data'][0]['name']
    size = response.json()['data'][0]['size']

    for conversation_id, conversation in sorted_conversations.items():
        # print(key, value)
        if conversation['messages'][0]['from'] == recipient_id:
            conversation_id = conversation_id
            break
        elif conversation['messages'][0]['to'] == recipient_id:
            conversation_id = conversation_id
            break

    sorted_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': '', 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': [{'type': f'{file_mime_type}', 'name': name, 'size': size, 'url': url}]})

    sort_conversations(conversation_id, platform)

    return {'type': f'{file_mime_type}', 'name': name, 'size': size, 'url': url}

    # return response.json()['attachment_id']

@app.route("/employees", methods=["GET"])
def employees():
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    if session['role'] == 1:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM pages')
        pages = cursor.fetchall()
        return render_template('employees.html', username=session['username'], role=session['role'], pages=pages)
    
@app.route("/getEmployees", methods=["GET"])
def get_employees():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT *, name as role FROM employees,roles WHERE employees.role_id = roles.id')
    # cursor.execute('SELECT * FROM employees')
    employees = cursor.fetchall()
    
    cursor.execute('SELECT ep.employee_id, ep.page_id, p.name FROM employee_pages ep, pages p WHERE ep.page_id = p.id')
    pages = cursor.fetchall()
    
    # Create a dictionary to store employees and their pages
    employee_pages = []

    # Populate the dictionary with employee information
    for employee in employees:
        employee_pages.append({
            'id': employee['id'],
            'username': employee['username'],
            'password': employee['password'],
            'role_id': employee['role_id'],
            'role': employee['role'],
            'pages': []
        })


    # Associate pages with employees
    # for page in pages:
    #     employee_id = page['employee_id']
    #     page_info = {
    #         'page_id': page['page_id'],
    #         'name': page['name']
    #     }
    #     employee_pages[employee_id]['pages'].append(page_info)

    for page in pages:
        employee_id = page['employee_id']
        page_info = {
            'page_id': page['page_id'],
            'name': page['name']
        }
        for employee in employee_pages:
            if employee['id'] == employee_id:
                employee['pages'].append(page_info)
                break

    print(tuple(employee_pages))
    return jsonify(tuple(employee_pages))
    
@app.route("/addEmployee", methods=["POST"])
def add_employee():
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    if session['role'] == 1:
        # print(request.form.getlist('pages[]'))
        # return 'success'
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        selected_pages = request.form.getlist('pages[]')

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('INSERT INTO employees (username, password, role_id) VALUES (%s, %s, %s)', (username, password, role))

        employee_id = cursor.lastrowid  # Get the ID of the newly inserted employee
        
        for page_id in selected_pages:
            cursor.execute('INSERT INTO employee_pages (employee_id, page_id) VALUES (%s, %s)', (employee_id, page_id))
        
        mysql.connection.commit()
        return 'success'
        # return redirect(url_for('employees'))

@app.route("/deleteEmployee/<employee_id>", methods=["POST"])
def delete_employee(employee_id):
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    if session['role'] == 1:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('DELETE FROM EMPLOYEES WHERE id = %s', (employee_id,))
        mysql.connection.commit()
        return 'success'
    
@app.route("/editEmployee/<employee_id>", methods=["POST"])
def edit_employee(employee_id):
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    if session['role'] == 1:
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE EMPLOYEES SET username = %s, password = %s, role_id = %s WHERE id = %s', (username, password, role, employee_id))
        mysql.connection.commit()
        return 'success'
    
@app.route("/sheets", methods=["GET"])
def sheets():
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    # if session['role'] == 1:
    # print(sh.worksheets()[0])
    sheets = []
    gc = gspread.service_account(filename='credentials.json')
    sh = gc.open('Sales')
    for sheet in sh.worksheets():
        sheets.append({'id': sheet.id, 'title': sheet.title})
    # text = str(sh.worksheets()[0])
    # id = sh.worksheets()[0].id
    # name = re.search(r"'(.*?)'", text).group(1)
    # for t in tmp:
    #     print(t)

    return render_template('sheets.html', username=session['username'], role=session['role'], sheets=sheets)

@app.route("/getSheets/<sheet_name>", methods=["GET"])
def getSheets(sheet_name):
    gc = gspread.service_account(filename='credentials.json')
    sh = gc.open('Sales')
    wks = sh.worksheet(unquote(sheet_name))
    data = wks.get_all_records()
    return data
    # return render_template('sheets.html')

@app.route("/addSale", methods=["POST"])
def add_sale():
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    # if session['role'] == 1:
    # print(request.form.getlist('pages[]'))
    # return 'success'
    name = request.form['name']
    date = request.form['date']
    clientName = request.form['clientName']
    contact = request.form['contact']
    email = request.form['email']
    projectName = request.form['projectName']
    product = request.form['product']
    received = request.form['received']
    source = request.form['source']
    totalCost = request.form['totalCost']
    upfront = request.form['upfront']
    remaining = request.form['remaining']
    status = request.form['status']
    remarks = request.form['remarks']
    # print(name, price, quantity, date, sheet_name)
    input_date = datetime.strptime(date, "%Y-%m-%d")
    # Format the date as "M/D/YY"
    date = f"{input_date.month}/{input_date.day}/{input_date.strftime('%Y')}"

    row_to_append = [name, date, clientName, contact, email, projectName, product, received, source, totalCost, upfront, remaining, status, remarks]

    gc = gspread.service_account(filename='credentials.json')
    sh = gc.open('Sales')
    wks = sh.worksheet('Total Sales')
    wks.append_row(row_to_append)
    return 'success'
    # return redirect(url_for('employees'))

@app.route("/pages", methods=["GET"])
def pages():
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    if session['role'] == 1:
        sheets = []
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open('Sales')
        for sheet in sh.worksheets():
            sheets.append({'id': sheet.id, 'title': sheet.title})
        return render_template('pages.html', username=session['username'], role=session['role'], sheets=sheets)
    
@app.route("/getPages", methods=["GET"])
def get_pages():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * from pages')
    # cursor.execute('SELECT * FROM employees')
    pages = cursor.fetchall()
    # print(employees)
    return jsonify(pages)
    
@app.route("/addPage", methods=["POST"])
def add_page():
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    if session['role'] == 1:
        # print(request.form.getlist('pages[]'))
        # return 'success'
        name = request.form['name']
        id = request.form['id']
        access_token = request.form['access_token']
        sheet = request.form['sheet']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('INSERT INTO pages VALUES (%s, %s, %s, %s)', (id, name, access_token, sheet))
        cursor.execute('INSERT INTO employee_pages (employee_id, page_id) VALUES (%s, %s)', (session['id'], id))

        mysql.connection.commit()
        return 'success'
        # return redirect(url_for('employees'))

@app.route("/deletePage/<page_id>", methods=["POST"])
def delete_page(page_id):
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    if session['role'] == 1:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('DELETE FROM pages WHERE id = %s', (page_id,))
        mysql.connection.commit()
        return 'success'
    
@app.route("/editPage/<page_id>", methods=["POST"])
def edit_page(page_id):
    if not session or not session['loggedin']:
        return redirect(url_for('login'))
    if session['role'] == 1:
        name = request.form['name']
        id = request.form['id']
        access_token = request.form['access_token']
        sheet = request.form['sheet']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('UPDATE pages SET id = %s, name = %s, access_token = %s, sheet = %s WHERE id = %s', (id, name, access_token, sheet, page_id))
        mysql.connection.commit()
        return 'success'
    
#routes for chat sharing
@app.route("/getEmployeesToAllowEnterChat", methods=["GET"])
def get_employees_to_allow_enter_chat():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM employees WHERE role_id = %s', (str(int(session['role']) + 1),))
    employees = cursor.fetchall()
    return jsonify(employees)

@app.route("/allowToEnterChat/<employee_id>/<conversation_id>/<timestamp>", methods=["POST"])
def allow_to_enter_chat(employee_id, conversation_id, timestamp):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('DELETE FROM chat_shares WHERE sender_id = %s AND receiver_id = %s AND conversation_id = %s', (session['id'], employee_id, conversation_id))
    mysql.connection.commit()
    cursor.execute('INSERT INTO chat_shares (sender_id, receiver_id, conversation_id, timestamp) VALUES(%s,%s,%s,%s)', (session['id'], employee_id, conversation_id, timestamp))
    mysql.connection.commit()
    cursor.execute('SELECT username FROM employees WHERE id = %s', (employee_id,))
    data = cursor.fetchone()
    return data['username']

@app.route("/unallowToEnterChat/<employee_id>/<conversation_id>/<timestamp>", methods=["POST"])
def unallow_to_enter_chat(employee_id, conversation_id, timestamp):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('DELETE FROM chat_shares WHERE sender_id = %s AND receiver_id = %s AND conversation_id = %s AND timestamp = %s', (session['id'], employee_id, conversation_id, timestamp))
    mysql.connection.commit()
    cursor.execute('SELECT username FROM employees WHERE id = %s', (employee_id,))
    data = cursor.fetchone()
    return data['username']

@app.route("/ifAllowed/<employee_id>/<conversation_id>/<timestamp>", methods=["GET"])
def if_allowed(employee_id, conversation_id, timestamp):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # print(message_id)
    cursor.execute('SELECT id FROM chat_shares WHERE sender_id = %s AND receiver_id = %s AND conversation_id = %s AND timestamp = %s', (session['id'], employee_id, conversation_id, timestamp))
    id = cursor.fetchone()
    return jsonify(id)

@app.route("/getContact/<user_id>", methods=["GET"])
def getContact(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM contacts WHERE id = %s', (user_id,))
    contact = cursor.fetchone()
    return jsonify(contact)

@app.route("/addContact", methods=["POST"])
def addContact():
    try:
        data = request.json
        # print(data['id'])
        id = data['id']
        name = data['name']
        phone = data['phone']
        email = data['email']
        month = data['month']
        day = data['day']
        address = data['address']
        city = data['city']
        state = data['state']
        postal_code = data['postalCode']
        page_id = data['pageId']
        project_name = data['projectName']
        product = data['product']

        cursor = mysql.connection.cursor()
        cursor.execute('INSERT INTO contacts VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)', (id, name, phone, email, month, day, address, city, state, postal_code, project_name, product))
        
        mysql.connection.commit()

        cursor.execute('SELECT sheet FROM pages WHERE id = %s', (page_id,))
        sheet = cursor.fetchone()[0]
        
        cursor.close()
        
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open('Sales')
        wks = sh.worksheet(sheet)

        # Read the existing data to find the last S.no
        existing_data = wks.get_all_records()
        
        # Assuming "S.no" is the column name
        last_sno = 0
        if existing_data:
            last_row = existing_data[-1]
            last_sno = int(last_row[next(iter(last_row))])

        # Calculate the next S.no
        next_sno = last_sno + 1

        # Get the current date
        current_date = datetime.now()

        # Format the date in M/D/YYYY format
        formatted_date = current_date.strftime('%m/%d/%Y')

        row_to_append = [next_sno, formatted_date, name, phone, email, project_name, product]

        wks.append_row(row_to_append)

        return jsonify({"message": "Contact added successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/editContact", methods=["POST"])
def editContact():
    try:
        data = request.json
        id = data['id']
        name = data['name']
        phone = data['phone']
        email = data['email']
        month = data['month']
        day = data['day']
        address = data['address']
        city = data['city']
        state = data['state']
        postal_code = data['postalCode']
        page_id = data['pageId']
        project_name = data['projectName']
        product = data['product']

        cursor = mysql.connection.cursor()
        cursor.execute('UPDATE contacts SET name = %s, phone = %s, email = %s, month = %s, day = %s, address = %s, city = %s, state = %s, postal_code = %s, project_name = %s, product = %s WHERE id = %s',
                       (name, phone, email, month, day, address, city, state, postal_code, project_name, product, id))
        
        mysql.connection.commit()
        
        cursor.execute('SELECT sheet FROM pages WHERE id = %s', (page_id,))
        sheet = cursor.fetchone()[0]

        cursor.close()
        
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open('Sales')
        wks = sh.worksheet(sheet)

        # Read the existing data to find the last S.no
        existing_data = wks.get_all_records()
        
        # Assuming "S.no" is the column name
        last_sno = 0
        if existing_data:
            last_row = existing_data[-1]
            last_sno = int(last_row[next(iter(last_row))])

        # Calculate the next S.no
        next_sno = last_sno + 1

        # Get the current date
        current_date = datetime.now()

        # Format the date in M/D/YYYY format
        formatted_date = current_date.strftime('%m/%d/%Y')

        row_to_append = [next_sno, formatted_date, name, phone, email, project_name, product]
        
        # Search for a row with the same name, phone, email, or project name
        for index, row in enumerate(existing_data):
            if (
                row["Client Name"] == name and name != ''
                or row["Contact"] == phone and phone != ''
                or row["Email"] == email and email != ''
                or row["Project Name"] == project_name and project_name != ''
            ):
                # Replace the existing row with the new data
                wks.delete_rows(index + 2)  # +2 because Google Sheets is 1-indexed, and we want to delete the correct row
                wks.insert_row(row_to_append, index=index + 2)  # Insert the new row in place
                break  # Exit the loop after the replacement
        else:
            # If no matching row is found, simply append the new row to the end
            wks.append_row(row_to_append)

        return jsonify({"message": "Contact edited successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)


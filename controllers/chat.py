from flask import Blueprint, session, redirect, url_for, render_template, request, jsonify


from datetime import datetime, timedelta
import json
import requests

# chats = Blueprint("chats", __name__)
FB_GRAPH_BASE_URL = 'https://graph.facebook.com/v17.0'

class AccessTokenManager:
    def __init__(self):
        self._access_token = None

    @property
    def access_token(self):
        return self._access_token

    @access_token.setter
    def access_token(self, value):
        self._access_token = value

token_manager = AccessTokenManager()

# mysql = None

# @chats.record
# def record_params(setup_state):
#     # This function is called when the blueprint is registered
#     # Initialize the MySQL extension using the Flask app instance
#     global mysql
#     mysql = MySQL(setup_state.app)

def process_conversations(mysql, data):
    if 'data' not in data:
        return {}, None
    
    try:
        next_page_url = data['paging']['next']
    except:
        next_page_url = None
        
    # while next_page_url:
    #     print('fayez')
    #     next_page_data = requests.get(next_page_url).json()
    #     data['data'].extend(next_page_data['data'])
    #     try:
    #         next_page_url = next_page_data['paging']['next']
    #     except:
    #         next_page_url = None

    # print('processing messages now')
            
    conversations = {}
    for conversation in data['data']:
        try:
            next_page_url_2 = conversation['messages']['paging']['next']
        except:
            next_page_url_2 = None

        # while next_page_url:
        #     next_page_data = requests.get(next_page_url).json()
        #     conversation['messages']['data'].extend(next_page_data['data'])
        #     try:
        #         next_page_url = next_page_data['paging']['next']
        #     except:
        #         next_page_url = None

        participants = conversation['participants']['data']
        messages = []
        for message in conversation['messages']['data']:
            # print(message)
            attachments = []
            if 'attachments' in message:
                for attachment in message['attachments']['data']:
                    # print(attachment)
                    name = attachment.get('name', '')
                    size = attachment.get('size', '')

                    if 'mime_type' not in attachment:
                        continue

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
                'read_timestamp': messages[0]['timestamp'],
                'next_page_url': next_page_url_2
            }
            conversations[conversation['id']] = conversation_dict

    cursor = mysql.cursor(dictionary=True)
    cursor.execute('SELECT * FROM message_reads')
    data = cursor.fetchall()
    # print(data)
    for x in data:
        if conversations.get(x['id']) != None:
            # print('fayez')
            conversations[x['id']]['read_timestamp'] = x['timestamp']

    return conversations, next_page_url

def process_messages(data):
    try:
        next_page_url = data['paging']['next']
    except:
        next_page_url = None

    messages = []
    for message in data['data']:
        # print(message)
        attachments = []
        if 'attachments' in message:
            for attachment in message['attachments']['data']:
                # print(attachment)
                name = attachment['name']
                try:
                    size = attachment['size']
                except:
                    size = ''
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
    return messages, next_page_url

def sort_conversations(conversation_id, platform):
    global sorted_conversations, messenger_conversations, instagram_conversations
    # sorted_conversations = dict(sorted(sorted_conversations.items(), key=lambda x: x[1]['messages'][0]['timestamp'], reverse=True))

    if platform == 'fb':
        tmp = messenger_conversations[conversation_id]
        if messenger_conversations.get(conversation_id) != None:
            del messenger_conversations[conversation_id]
        messenger_conversations = {conversation_id: tmp, **messenger_conversations}
    elif platform == 'insta':
        tmp = instagram_conversations[conversation_id]
        if instagram_conversations.get(conversation_id) != None:
            del instagram_conversations[conversation_id]
        instagram_conversations = {conversation_id: tmp, **instagram_conversations}
    elif platform == 'all':
        tmp = sorted_conversations[conversation_id]
        if sorted_conversations.get(conversation_id) != None:
            del sorted_conversations[conversation_id]
        sorted_conversations = {conversation_id: tmp, **sorted_conversations}

def getConversationDict(mysql, page_id, page_access_token, platform = None):
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
    instagram_data = instagram_conversations.json()
    instagram_conversations, next_instagram_page_url = process_conversations(mysql, instagram_data)
    # return instagram_conversations
    
    # elif platform == 'fb':
    # Retrieve conversations from Messenger
    messenger_params = conversations_params.copy()

    messenger_conversations = requests.get(
        f'{FB_GRAPH_BASE_URL}/{page_id}/conversations',
        params=messenger_params
    )
    # print(messenger_conversations.json())
    messenger_data = messenger_conversations.json()
    messenger_conversations, next_messenger_page_url = process_conversations(mysql, messenger_data)
    # return messenger_conversations

    if platform == 'insta':
        return messenger_conversations, next_instagram_page_url
    elif platform == 'fb':
        return messenger_conversations, next_messenger_page_url
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

def chat(mysql, page_id):
    # pages = []
    # if session['role'] == 2:
    # cursor = current_app.mysql.cursor(dictionary=True)
    # cursor.execute('SELECT * FROM pages WHERE id IN (SELECT page_id FROM employee_pages WHERE employee_id = %s)', (session['id'],))
    # pages = cursor.fetchall()
    # print(pages)
    # for x in data:
    #     pages.append(x['page_id'])

    cursor = mysql.cursor(dictionary=True)
    cursor.execute('SELECT page_name, access_token FROM pages WHERE page_id = %s', (page_id,))
    data = cursor.fetchone()
    # print(data)
    access_token = data['access_token']
    # session['access_token'] = access_token

    token_manager.access_token = access_token

    # global PAGE_ACCESS_TOKEN
    # PAGE_ACCESS_TOKEN = access_token
    
    page_name = data['page_name']

    return render_template('chat.html', username=session['username'], role=session['role'], page_id=page_id, page_name=page_name, access_token=access_token)
    
def privacy():
    return render_template('privacy.html')

def get_pages(mysql):
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('SELECT * FROM pages WHERE id IN (SELECT page_id FROM employee_pages WHERE employee_id = %s)', (session['id'],))
    data = cursor.fetchall()
    # for row in data:
    #     row['url'] = r"{{ url_for('chat', page_id=' + row['id'] + ') }}"
    # print(data)
    return jsonify(data)
    
# def getIds():
#     return {'page_id': PAGE_ID, 'insta_id': INSTA_ID}

def get_conversations(mysql, page_id, page_access_token, platform):
    # print(session['role'])
    # global sorted_conversations, messenger_conversations, instagram_conversations
    # global PAGE_ID, PAGE_ACCESS_TOKEN
    # PAGE_ID = page_id
    # PAGE_ACCESS_TOKEN = page_access_token
    if session['role'] == 1:
        if platform == 'fb':
            messenger_conversations, next_messenger_page_url = getConversationDict(mysql, page_id, page_access_token, platform)
            result = [{'id': conv_id, 'name': details['name'], 'recipient_id': details['id'], 'last_message': details['messages'][0]['message'], 'sender': details['messages'][0]['from'], 'timestamp': details['messages'][0]['timestamp'], 'read_timestamp': details['read_timestamp']} for conv_id,details in messenger_conversations.items()]
            result.append(next_messenger_page_url)
            return result
        elif platform == 'insta':
            instagram_conversations, next_instagram_page_url = getConversationDict(mysql, page_id, page_access_token, platform)
            return [{'id': conv_id, 'name': details['name'], 'last_message': details['messages'][0]['message'], 'sender': details['messages'][0]['from'], 'timestamp': details['messages'][0]['timestamp'], 'read_timestamp': details['read_timestamp']} for conv_id,details in instagram_conversations.items()], next_instagram_page_url
        elif platform == 'all':
            sorted_conversations = getConversationDict(mysql, page_id, page_access_token)
            return [{'id': conv_id, 'name': details['name'], 'last_message': details['messages'][0]['message'], 'sender': details['messages'][0]['from'], 'timestamp': details['messages'][0]['timestamp'], 'read_timestamp': details['read_timestamp']} for conv_id,details in sorted_conversations.items()]
    elif session['role'] == 2:
        # print(page_access_token)
        # print(PAGE_ACCESS_TOKEN)
        sorted_conversations = getConversationDict(mysql, page_id, page_access_token)
        # print(conversations)
        return [{'id': conv_id, 'name': details['name'], 'last_message': details['messages'][0]['message'], 'sender': details['messages'][0]['from'], 'timestamp': details['messages'][0]['timestamp'], 'read_timestamp': details['read_timestamp']} for conv_id,details in sorted_conversations.items()]
    # elif session['role'] > 2:
    #     cursor = current_app.mysql.cursor(dictionary=True)
    #     cursor.execute('SELECT conversation_id FROM chat_shares WHERE receiver_id = %s', (session['id'],))
    #     data = cursor.fetchall()
    #     # print(data)
    #     convs = []
    #     for x in data:
    #         convs.append({'id': x['conversation_id'], 'name': sorted_conversations[x['conversation_id']]['name'], 'last_message': sorted_conversations[x['conversation_id']]['messages'][0]['message'], 'sender': sorted_conversations[x['conversation_id']]['messages'][0]['from'], 'timestamp': sorted_conversations[x['conversation_id']]['messages'][0]['timestamp'], 'read_timestamp': sorted_conversations[x['conversation_id']]['read_timestamp']})
    #     # return [{'id': conv_id, 'name': details['name']} for conv_id,details in conversations.items()]
    #     return convs
    
def get_more_conversations(mysql):
    page_url = request.args.get('page_url')
    platform = request.args.get('platform')

    next_page_data = requests.get(page_url).json()
    temporary_conversations, next_page_url = process_conversations(mysql, next_page_data)
    # print(next_page_url)
    # print(temporary_conversations)
    # print(sorted_conversations)

    # global sorted_conversations, messenger_conversations, instagram_conversations
    # for id,conversation in temporary_conversations.items():
    #     if platform == 'fb':
    #         messenger_conversations[id] = conversation
    #     elif platform == 'insta':
    #         instagram_conversations[id] = conversation
    #     elif platform == 'all':
    #         sorted_conversations[id] = conversation

    result = [{'id': conv_id, 'name': details['name'], 'last_message': details['messages'][0]['message'], 'sender': details['messages'][0]['from'], 'timestamp': details['messages'][0]['timestamp'], 'read_timestamp': details['read_timestamp']} for conv_id,details in temporary_conversations.items()]
    result.append(next_page_url)
    return result

def get_messages(mysql, conversation_id, page_access_token, platform):
    # conversations = sorted_conversations

    # try:
    #     if platform == 'fb':
    #         messenger_conversations[conversation_id]['read_timestamp'] = messenger_conversations[conversation_id]['messages'][0]['timestamp'] 
    #         temporary_conversations = messenger_conversations
    #     elif platform == 'insta':
    #         instagram_conversations[conversation_id]['read_timestamp'] = instagram_conversations[conversation_id]['messages'][0]['timestamp'] 
    #         temporary_conversations = instagram_conversations
    #     elif platform == 'all':
    #         sorted_conversations[conversation_id]['read_timestamp'] = sorted_conversations[conversation_id]['messages'][0]['timestamp'] 
    #         temporary_conversations = sorted_conversations
    # except:
    conversations_params = {
        'fields': 'participants, messages{id,message,created_time,from,to,attachments}',
        'access_token': page_access_token,
    }

    if platform == 'insta':
        conversations_params['platform'] = 'instagram'

    conversations = requests.get(
        f'{FB_GRAPH_BASE_URL}/{conversation_id}',
        params=conversations_params
    )
    # print(conversations.json())
    # instagram_data = instagram_conversations.json()
    conversations_data = {}
    conversations_data['data'] = [conversations.json()]
    temporary_conversations, _ = process_conversations(mysql, conversations_data)
    # print(temporary_conversations)

    cursor = mysql.cursor(dictionary=True)
    cursor.execute('SELECT timestamp FROM message_reads WHERE id = %s', (conversation_id,))
    data = cursor.fetchone()
    
    if data and data['timestamp'] != temporary_conversations[conversation_id]['messages'][0]['timestamp']:
        cursor.execute('UPDATE message_reads SET timestamp = %s where id = %s', (temporary_conversations[conversation_id]['messages'][0]['timestamp'],conversation_id))
    elif data == None:
        cursor.execute('INSERT INTO message_reads (id, timestamp) VALUES (%s, %s)', (conversation_id, temporary_conversations[conversation_id]['messages'][0]['timestamp']))
    mysql.commit()

    if session['role'] == 1 or session['role'] == 2:
        # print( conversations[conversation_id])
        cursor = mysql.cursor(dictionary=True)
        # print(sorted_conversations)
        cursor.execute('SELECT * FROM contacts WHERE id = %s', (temporary_conversations[conversation_id]['id'],))
        data = cursor.fetchone()
        return [{"id": temporary_conversations[conversation_id]['id'], "name": temporary_conversations[conversation_id]['name']}, temporary_conversations[conversation_id]['messages'], data, temporary_conversations[conversation_id]['next_page_url']]
    # elif session['role'] > 2:
    #     cursor = current_app.mysql.cursor(dictionary=True)
    #     cursor.execute('SELECT timestamp FROM chat_shares WHERE receiver_id = %s AND conversation_id = %s', (session['id'], conversation_id))
    #     data = cursor.fetchone()
    #     # print(data)
    #     timestamp = data['timestamp'] if data != None else ''
    #     print(timestamp)
    #     messages = []

    #     for message in temporary_conversations[conversation_id]['messages']:
    #         # print(message['timestamp'], timestamp)
    #         if message['timestamp'] > timestamp:
    #             messages.append(message)

    #     return [{"id": temporary_conversations[conversation_id]['id'], "name": temporary_conversations[conversation_id]['name']}, messages]
    
def get_more_messages():
    conversation_id = request.args.get('conversation_id')
    page_url = request.args.get('page_url')
    platform = request.args.get('platform')

    next_page_data = requests.get(page_url).json()
    temporary_messages, next_page_url = process_messages(next_page_data)

    # global sorted_conversations, messenger_conversations, instagram_conversations

    # try:
    #     if platform == 'fb':
    #         messenger_conversations[conversation_id]['messages'].extend(temporary_messages)
    #         messenger_conversations[conversation_id]['next_page_url'] = next_page_url
    #     elif platform == 'insta':
    #         instagram_conversations[conversation_id]['messages'].extend(temporary_messages)
    #         instagram_conversations[conversation_id]['next_page_url'] = next_page_url
    #     elif platform == 'all':
    #         sorted_conversations[conversation_id]['messages'].extend(temporary_messages)
    #         sorted_conversations[conversation_id]['next_page_url'] = next_page_url
    # except:
    #     pass

    return [temporary_messages, next_page_url]

def check_message():
    global message_received
    if message_received:
        tmp = message_received
        message_received = {}
        print('fayez')
        print(tmp)
        return jsonify(tmp)
    return 'no message received'

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
    # global PAGE_ACCESS_TOKEN
    # print(session)

    response = requests.get(f'{FB_GRAPH_BASE_URL}/{message_id}/attachments', params={'access_token': token_manager.access_token})
    
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

    # conversations_params = {
    #     'fields': 'participants',
    #     'user_id': sender_id,
    #     'platform': p,
    #     'access_token': PAGE_ACCESS_TOKEN,
    # }

    # response = requests.get(
    #     f"{FB_GRAPH_BASE_URL}/{PAGE_ID}/conversations",
    #     params=conversations_params
    # )
    # print(response.json())

    # try:
    #     conversation_id = response.json()['data'][0]['id']
    #     # print(conversation_id)
    #     if p == 'messenger':
    #         sender_name = response.json()['data'][0]['participants']['data'][0]['name']
    #     else:
    #         sender_name = response.json()['data'][0]['participants']['data'][1]['username']
    #         # print(sender_name)
    #     # print(conversation_id)

    #     # global sorted_conversations

    #     timestamp = datetime.utcnow()
    #     timestamp_plus_one_second = timestamp + timedelta(seconds=1)
    #     timestamp = timestamp_plus_one_second.strftime('%Y-%m-%dT%H:%M:%S+0000')

    #     if platform == 'fb':
    #         if messenger_conversations.get(conversation_id) != None:
    #             messenger_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment})
    #         else:
    #             messenger_conversations[conversation_id] = {'id': sender_id, 'name': sender_name, 'messages': [{'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment}]}
    #     elif platform == 'insta':
    #         if instagram_conversations.get(conversation_id) != None:
    #             instagram_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment})
    #         else:
    #             instagram_conversations[conversation_id] = {'id': sender_id, 'name': sender_name, 'messages': [{'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment}]}
    #     elif platform == 'all':
    #         if sorted_conversations.get(conversation_id) != None:
    #             sorted_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment})
    #         else:
    #             sorted_conversations[conversation_id] = {'id': sender_id, 'name': sender_name, 'messages': [{'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment}]}

    #     sort_conversations(conversation_id, platform)
    # except:
    #     conversation_id = ''
    #     sender_name = ''
    #     timestamp = datetime.utcnow()
    #     timestamp_plus_one_second = timestamp + timedelta(seconds=1)
    #     timestamp = timestamp_plus_one_second.strftime('%Y-%m-%dT%H:%M:%S+0000')
    #     pass

    conversations_params = {
        'fields': 'participants',
        'user_id': sender_id,
        'platform': p,
        'access_token': token_manager.access_token,
    }

    response = requests.get(
        f"{FB_GRAPH_BASE_URL}/me/conversations",
        params=conversations_params
    )
    print(response.json())

    try:
        conversation_id = response.json()['data'][0]['id']
    except:
        conversation_id = ''

    # conversation_id = ''
    sender_name = ''
    timestamp = datetime.utcnow()
    timestamp_plus_one_second = timestamp + timedelta(seconds=1)
    timestamp = timestamp_plus_one_second.strftime('%Y-%m-%dT%H:%M:%S+0000')
    
    # socketio.emit('message_received', {'data': {'id': sender_id, 'name': sender_name, 'messages': [{'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment}]}})
    global message_received
    message_received = {'data': {'conversation_id': conversation_id, 'id': sender_id, 'name': sender_name, 'messages': [{'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': sender_id, 'to': receiver_id, 'attachments': attachment}]}}

    return timestamp

def send_message():
    message = request.form['message']
    recipient_id = request.form['recipient_id']
    platform = request.form['platform']
    page_id = request.form['page_id']
    page_access_token = request.form['page_access_token']
    
    message_params = {
        'recipient': json.dumps({'id': recipient_id}),
        'message': json.dumps({
            'text': message,
        }),
        'messaging_type': 'RESPONSE',
        'access_token': page_access_token,
    }

    response = requests.post(
        f"{FB_GRAPH_BASE_URL}/{page_id}/messages",
        params=message_params
    )

    message_id = response.json()['message_id']

    # try:
    #     message_id = response.json()['message_id']
    # except:
    #     message_params = {
    #         'recipient': json.dumps({'id': recipient_id}),
    #         'message': json.dumps({
    #             'text': message,
    #         }),
    #         'messaging_type': 'MESSAGE_TAG',
    #         'tag': 'ACCOUNT_UPDATE',
    #         'access_token': page_access_token,
    #     }

    #     response = requests.post(
    #         f"{FB_GRAPH_BASE_URL}/{page_id}/messages",
    #         params=message_params
    #     )

    #     message_id = response.json()['message_id']

    timestamp = datetime.utcnow()
    timestamp_plus_one_second = timestamp + timedelta(seconds=1)
    timestamp = timestamp_plus_one_second.strftime('%Y-%m-%dT%H:%M:%S+0000')
    # print('Time Sent: ', timestamp)
    # print(response.json())
    # message_id = response.json()['message_id']

    # # response = requests.get(f'https://graph.facebook.com/v13.0/{message_id}',
    # #                     params={'access_token': PAGE_ACCESS_TOKEN})
    # # data = response.json()
    # # timestamp = data['created_time']
    # # print('Time Sent: ', timestamp)

    # # print(response.json())
    # if platform == 'fb':
    #     temporary_conversations = messenger_conversations
    # elif platform == 'insta':
    #     temporary_conversations = instagram_conversations
    # elif platform == 'all':
    #     temporary_conversations = sorted_conversations

    # for conversation_id, conversation in temporary_conversations.items():
    #     # print(key, value)
    #     if conversation['messages'][0]['from'] == recipient_id:
    #         conversation_id = conversation_id
    #         break
    #     elif conversation['messages'][0]['to'] == recipient_id:
    #         conversation_id = conversation_id
    #         break

    # # conversation_id = ''
    # # print(conversation_id)
    
    # if platform == 'fb':
    #     messenger_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': []})
    # elif platform == 'insta':
    #     instagram_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': []})
    # elif platform == 'all':
    #     sorted_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': []})
    
    # # if platform == 'fb':
    # #     messenger_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': []})
    # # elif platform == 'insta':
    # #     instagram_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': message, 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': []})

    # # global sorted_conversations
    # # if sorted_conversations.get(conversation_id) != None:
    # #     sorted_conversations[conversation_id]['messages'].insert(0, {'message': message, 'from': sender_id, 'to': receiver_id, 'attachments': attachment})

    # sort_conversations(conversation_id, platform)

    return timestamp

def send_attachment():
    url = "https://graph.facebook.com/v17.0/me/message_attachments"

    recipient_id = request.form['recipient_id']
    file = request.files['file']
    platform = request.form['platform']
    page_id = request.form['page_id']
    page_access_token = request.form['page_access_token']
    # print(file.filename)
    # access_token = "<PAGE_ACCESS_TOKEN>"
    # file_path = r"C:\Users\USER\Desktop\example.png"

    allowed_image_extensions = ('png', 'jpg', 'jpeg', 'gif')
    allowed_video_extensions = ('mp4', 'avi', 'mov')
    allowed_zip_extensions = ('zip', 'rar')
    
    file_extension = file.filename.lower().split('.')[-1]
    # print(file_extension)
    if file_extension in allowed_image_extensions:
        attachment_type = "image"
        file_mime_type = "image/png"  # Update with appropriate image mime type
    elif file_extension in allowed_video_extensions:
        attachment_type = "video"
        file_mime_type = "video/mp4"  # Update with appropriate video mime type
    elif file_extension in allowed_zip_extensions:
        attachment_type = "file"
        file_mime_type = "application/zip"  # Update with appropriate zip mime type
    # else:
    #     return "Unsupported file type"
    # print(attachment_type, file_mime_type)
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
        "access_token": page_access_token
    }

    response = requests.post(url, params=params, files=files, data={"message": json.dumps(message)})
    print(response.json())
    # try:
    attachment_id = response.json()['attachment_id']
    # except:
    #      return response.json()
    
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
        'access_token': page_access_token,
    }

    response = requests.post(
        f"{FB_GRAPH_BASE_URL}/{page_id}/messages",
        params=message_params
    )

    timestamp = datetime.utcnow()
    timestamp_plus_one_second = timestamp + timedelta(seconds=1)
    timestamp = timestamp_plus_one_second.strftime('%Y-%m-%dT%H:%M:%S+0000')

    print(response.json())

    message_id = response.json()['message_id']

    params = {
        # 'fields': 'image_data',
        'access_token': page_access_token,
    }

    response = requests.get(f'{FB_GRAPH_BASE_URL}/{message_id}/attachments', params=params)
    print(response.json())
    # print(file.content_length)
    if attachment_type == 'image' or attachment_type == 'video':
        url = response.json()['data'][0][f'{attachment_type}_data']['url']
    else:
        url = response.json()['data'][0]['file_url']
    # print(image_url)

    name = response.json()['data'][0]['name']
    size = response.json()['data'][0]['size']

    # if platform == 'fb':
    #     temporary_conversations = messenger_conversations
    # elif platform == 'insta':
    #     temporary_conversations = instagram_conversations
    # elif platform == 'all':
    #     temporary_conversations = sorted_conversations

    # for conversation_id, conversation in temporary_conversations.items():
    #     # print(key, value)
    #     if conversation['messages'][0]['from'] == recipient_id:
    #         conversation_id = conversation_id
    #         break
    #     elif conversation['messages'][0]['to'] == recipient_id:
    #         conversation_id = conversation_id
    #         break

    # if platform == 'fb':
    #     messenger_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': '', 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': [{'type': f'{file_mime_type}', 'name': name, 'size': size, 'url': url}]})
    # elif platform == 'insta':
    #     instagram_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': '', 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': [{'type': f'{file_mime_type}', 'name': name, 'size': size, 'url': url}]})
    # elif platform == 'all':
    #     sorted_conversations[conversation_id]['messages'].insert(0, {'message_id': message_id, 'message': '', 'timestamp': timestamp, 'from': '114887508325720', 'to': recipient_id, 'attachments': [{'type': f'{file_mime_type}', 'name': name, 'size': size, 'url': url}]})

    # sort_conversations(conversation_id, platform)

    return {'type': f'{file_mime_type}', 'name': name, 'size': size, 'url': url}

    # return response.json()['attachment_id']
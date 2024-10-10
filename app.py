from flask import Flask, session, redirect, url_for, request
import secrets
import mysql.connector
from controllers import auth, employee, page, sheet, contact, chatshare, chat
from datetime import timedelta

app = Flask(__name__)

app.secret_key = 'b7c8mntcrm2e3f5a1mntcrm4d9mntcrm6fe3'

def connect():
    sql = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="crm"
    )

    return sql

# Middleware to check if the user is logged in before each request
@app.before_request
def middlewares():
    # List of routes that don't require login
    # excluded_routes = ['login', 'privacy', 'receiveMessage', 'checkMessage', 'sendAttachment', 'send_message', 'getMessages', 'getMoreMessages', 'getConversations', 'getMoreConversations', 'getContact', 'addContact', 'editContact', 'addSale', 'getSheets', 'getEmployees', 'getPages', 'get_pages', 'get_contact', 'get_conversations', 'get_more_conversations', 'get_messages', 'get_more_messages', 'check_message', 'receive_message', 'send_message', 'send_attachment']
    incuded_routes = ['index', 'logout', 'employees', 'addEmployee', 'deleteEmployee', 'editEmployee', 'pages', 'addPage', 'deletePage', 'editPage', 'sheets']
    # print(request.endpoint)

    if not session.get('loggedin') and (request.endpoint in incuded_routes or request.endpoint.startswith('chat')):
        return redirect(url_for('login'))
    
    if session.get('loggedin') and request.endpoint == 'login':
        return redirect(url_for('index'))
    
    if session.get('role') != 1 and ('page' in request.endpoint or 'employee' in request.endpoint):
        return redirect(url_for('index'))
        

#auth routes
@app.route('/')
def index():
    return auth.index()

@app.route('/login', methods=["GET", "POST"])
def login():
    return auth.login(connect())

@app.route('/logout', methods=["POST"])
def logout():
    return auth.logout()
#end auth routes

#employee routes
@app.route("/employees", methods=["GET"])
def employees():
    return employee.employees(connect())

@app.route("/getEmployees", methods=["GET"])
def get_employees():
    return employee.get_employees(connect())

@app.route("/addEmployee", methods=["POST"])
def add_employee():
    return employee.add_employee(connect())

@app.route("/deleteEmployee/<employee_id>", methods=["POST"])
def delete_employee(employee_id):
    return employee.delete_employee(connect(), employee_id)

@app.route("/editEmployee/<employee_id>", methods=["POST"])
def edit_employee(employee_id):
    return employee.edit_employee(connect(), employee_id)
#end employee routes

#page routes
@app.route("/pages", methods=["GET"])
def pages():
    return page.pages()

@app.route("/getPages", methods=["GET"])
def get_pages():
    return page.get_pages(connect())

@app.route("/addPage", methods=["POST"])
def add_page():
    return page.add_page(connect())

@app.route("/deletePage/<id>", methods=["POST"])
def delete_page(id):
    return page.delete_page(connect(), id)

@app.route("/editPage/<id>", methods=["POST"])
def edit_page(id):
    return page.edit_page(connect(), id)
#end page routes

#sheet routes
@app.route("/sheets", methods=["GET"])
def sheets():
    return sheet.sheets()

@app.route("/getSheets/<sheet_name>", methods=["GET"])
def get_sheets(sheet_name):
    return sheet.get_sheets(sheet_name)

@app.route("/addSale", methods=["POST"])
def add_sale():
    return sheet.add_sale()
#end sheet routes

#contact routes
@app.route("/getContact/<user_id>", methods=["GET"])
def get_contact(user_id):
    return contact.get_contact(connect(), user_id)

@app.route("/addContact", methods=["POST"])
def add_contact():
    return contact.add_contact(connect())

@app.route("/editContact", methods=["POST"])
def edit_contact():
    return contact.edit_contact(connect())
#end contact routes

#chat routes
@app.route('/chat/<page_id>', methods=['GET'])
def chats(page_id):
    return chat.chat(connect(), page_id)

@app.route('/privacy', methods=['GET'])
def privacy():
    return chat.privacy()

@app.route('/getConversations/<page_id>/<page_access_token>/<platform>', methods=['GET'])
def get_conversations(page_id, page_access_token, platform):
    return chat.get_conversations(connect(), page_id, page_access_token, platform)

@app.route('/getMoreConversations', methods=['GET'])
def get_more_conversations():
    return chat.get_more_conversations(connect())

@app.route('/getMessages/<conversation_id>/<page_access_token>/<platform>', methods=['GET'])
def get_messages(conversation_id, page_access_token, platform):
    return chat.get_messages(connect(), conversation_id, page_access_token, platform)

@app.route('/getMoreMessages', methods=['GET'])
def get_more_messages():
    return chat.get_more_messages()

@app.route("/checkMessage", methods=["GET", "POST"])
def check_message():
    return chat.check_message()

@app.route("/receiveMessage", methods=["GET", "POST"])
def receive_message():
    return chat.receive_message()

@app.route("/sendMessage", methods=["POST"])
def send_message():
    return chat.send_message()

@app.route("/sendAttachment", methods=["POST"])
def send_attachment():
    return chat.send_attachment()
#end chat routes

if __name__ == "__main__":
    app.run(debug=True)
    # app.run(debug=False, use_reloader=False)

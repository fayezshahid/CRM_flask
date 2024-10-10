from flask import Blueprint, session, jsonify

chatshare = Blueprint("chatshare", __name__)
mysql = None

@chatshare.record
def record_params(setup_state):
    # This function is called when the blueprint is registered
    # Initialize the MySQL extension using the Flask app instance
    global mysql
    mysql = MySQL(setup_state.app)

#routes for chat sharing
@chatshare.route("/getEmployeesToAllowEnterChat", methods=["GET"])
def get_employees_to_allow_enter_chat():
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('SELECT * FROM employees WHERE role_id = %s', (str(int(session['role']) + 1),))
    employees = cursor.fetchall()
    return jsonify(employees)

@chatshare.route("/allowToEnterChat/<employee_id>/<conversation_id>/<timestamp>", methods=["POST"])
def allow_to_enter_chat(employee_id, conversation_id, timestamp):
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('DELETE FROM chat_shares WHERE sender_id = %s AND receiver_id = %s AND conversation_id = %s', (session['id'], employee_id, conversation_id))
    mysql.commit()
    cursor.execute('INSERT INTO chat_shares (sender_id, receiver_id, conversation_id, timestamp) VALUES(%s,%s,%s,%s)', (session['id'], employee_id, conversation_id, timestamp))
    mysql.commit()
    cursor.execute('SELECT username FROM employees WHERE id = %s', (employee_id,))
    data = cursor.fetchone()
    return data['username']

@chatshare.route("/unallowToEnterChat/<employee_id>/<conversation_id>/<timestamp>", methods=["POST"])
def unallow_to_enter_chat(employee_id, conversation_id, timestamp):
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('DELETE FROM chat_shares WHERE sender_id = %s AND receiver_id = %s AND conversation_id = %s AND timestamp = %s', (session['id'], employee_id, conversation_id, timestamp))
    mysql.commit()
    cursor.execute('SELECT username FROM employees WHERE id = %s', (employee_id,))
    data = cursor.fetchone()
    return data['username']

@chatshare.route("/ifAllowed/<employee_id>/<conversation_id>/<timestamp>", methods=["GET"])
def if_allowed(employee_id, conversation_id, timestamp):
    cursor = mysql.cursor(dictionary=True)
    # print(message_id)
    cursor.execute('SELECT id FROM chat_shares WHERE sender_id = %s AND receiver_id = %s AND conversation_id = %s AND timestamp = %s', (session['id'], employee_id, conversation_id, timestamp))
    id = cursor.fetchone()
    return jsonify(id)
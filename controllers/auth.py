from flask import Blueprint, session, redirect, url_for, render_template, request

def index():
    return render_template('index.html', username=session['username'], role=session['role'])

def login(mysql):
    msg = ''
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form and 'role' in request.form:
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        cursor = mysql.cursor(dictionary=True)
        cursor.execute('SELECT * FROM employees WHERE username = %s AND password = %s AND role_id = %s', (username, password, role))
        account = cursor.fetchone()
        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            session['role'] = account['role_id']
            msg = 'Logged in successfully !'
            return redirect(url_for('index'))
        else:
            msg = 'Incorrect username / password !'
    return render_template('login.html', msg=msg)
    
def logout():
    session['loggedin'] = False
    session.pop('id', None)
    session.pop('email', None)
    session.pop('name', None)
    return redirect(url_for('login'))
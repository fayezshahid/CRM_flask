from flask import Blueprint, session, redirect, url_for, render_template, request, jsonify

def employees(mysql):
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('SELECT * FROM pages')
    pages = cursor.fetchall()
    return render_template('employees.html', username=session['username'], role=session['role'], pages=pages)
    
def get_employees(mysql):
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('SELECT ep.*, r.name as role FROM employees ep, roles r WHERE ep.role_id = r.id')
    employees = cursor.fetchall()

    cursor.execute('SELECT ep.employee_id, ep.page_id, p.page_name FROM employee_pages ep, pages p WHERE ep.page_id = p.id')
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

    for page in pages:
        employee_id = page['employee_id']
        page_info = {
            'page_id': page['page_id'],
            'name': page['page_name']
        }
        for employee in employee_pages:
            if employee['id'] == employee_id:
                employee['pages'].append(page_info)
                break

    # print(tuple(employee_pages))
    return jsonify(tuple(employee_pages))
    
def add_employee(mysql):
    # print(request.form.getlist('pages[]'))
    # return 'success'
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']
    selected_pages = request.form.getlist('pages[]')

    cursor = mysql.cursor(dictionary=True)
    cursor.execute('INSERT INTO employees (username, password, role_id) VALUES (%s, %s, %s)', (username, password, role))

    employee_id = cursor.lastrowid  # Get the ID of the newly inserted employee
    
    for page_id in selected_pages:
        cursor.execute('INSERT INTO employee_pages (employee_id, page_id) VALUES (%s, %s)', (employee_id, page_id))
    
    mysql.commit()
    return 'success'
    # return redirect(url_for('employees'))

def delete_employee(mysql, employee_id):
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('DELETE FROM employees WHERE id = %s', (employee_id,))
    mysql.commit()
    return 'success'
    
def edit_employee(mysql, employee_id):
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']
    selected_pages = request.form.getlist('pages[]')

    cursor = mysql.cursor(dictionary=True)
    
    # Update employee details
    cursor.execute('UPDATE employees SET username = %s, password = %s, role_id = %s WHERE id = %s', (username, password, role, employee_id))

    # Delete existing employee-page associations
    cursor.execute('DELETE FROM employee_pages WHERE employee_id = %s', (employee_id,))
    
    # Insert updated employee-page associations
    for page_id in selected_pages:
        cursor.execute('INSERT INTO employee_pages (employee_id, page_id) VALUES (%s, %s)', (employee_id, page_id))
    
    mysql.commit()
    return 'success'

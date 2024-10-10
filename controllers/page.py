from flask import Blueprint, session, redirect, url_for, render_template, request, jsonify
import gspread

google_sheet_name = 'Lead Sheet'

def pages():
    sheets = []
    gc = gspread.service_account(filename='credentials.json')
    sh = gc.open(google_sheet_name)
    for sheet in sh.worksheets():
        sheets.append({'id': sheet.id, 'title': sheet.title})
    return render_template('pages.html', username=session['username'], role=session['role'], sheets=sheets)
    
def get_pages(mysql):
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('SELECT * from pages')
    # cursor.execute('SELECT * FROM employees')
    pages = cursor.fetchall()
    # print(employees)
    return jsonify(pages)
    
def add_page(mysql):
    # print(request.form.getlist('pages[]'))
    # return 'success'
    page_name = request.form['page_name']
    page_id = request.form['page_id']
    access_token = request.form['access_token']
    sheet = request.form.get('sheet', '')

    cursor = mysql.cursor(dictionary=True)
    cursor.execute('INSERT INTO pages (page_id, page_name, access_token, sheet) VALUES (%s, %s, %s, %s)', (page_id, page_name, access_token, sheet))
    inserted_id = cursor.lastrowid
    cursor.execute('INSERT INTO employee_pages (employee_id, page_id) VALUES (%s, %s)', (session['id'], inserted_id))

    mysql.commit()
    return 'success'
    # return redirect(url_for('employees'))

def delete_page(mysql, id):
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('DELETE FROM pages WHERE id = %s', (id,))
    mysql.commit()
    return 'success'
    
def edit_page(mysql, id):
    page_name = request.form['page_name']
    page_id = request.form['page_id']
    access_token = request.form['access_token']
    sheet = request.form['sheet']
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('UPDATE pages SET page_id = %s, page_name = %s, access_token = %s, sheet = %s WHERE id = %s', (page_id, page_name, access_token, sheet, id))
    mysql.commit()
    return 'success'
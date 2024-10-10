from flask import Blueprint, session, redirect, url_for, render_template, request, jsonify

import gspread
from datetime import datetime

from .page import google_sheet_name

def get_contact(mysql, user_id):
    cursor = mysql.cursor(dictionary=True)
    cursor.execute('SELECT * FROM contacts WHERE id = %s', (user_id,))
    contact = cursor.fetchone()
    return jsonify(contact)

def add_contact(mysql):
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
        
        mysql.commit()

        cursor.execute('SELECT sheet FROM pages WHERE id = %s', (page_id,))
        sheet = cursor.fetchone()[0]
        
        cursor.close()
        
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open(google_sheet_name)
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
    
def edit_contact(mysql):
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
        
        mysql.commit()
        
        cursor.execute('SELECT sheet FROM pages WHERE id = %s', (page_id,))
        sheet = cursor.fetchone()[0]

        cursor.close()
        
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open(google_sheet_name)
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
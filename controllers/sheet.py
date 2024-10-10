from flask import Blueprint, session, redirect, url_for, render_template, request
from urllib.parse import unquote
import gspread
from gspread.exceptions import GSpreadException
from datetime import datetime
from .page import google_sheet_name
from collections import OrderedDict

def sheets():
    sheets = []
    gc = gspread.service_account(filename='credentials.json')
    sh = gc.open(google_sheet_name)
    for sheet in sh.worksheets():
        sheets.append({'id': sheet.id, 'title': sheet.title})

    return render_template('sheets.html', username=session['username'], role=session['role'], sheets=sheets)

def get_sheets(sheet_name):
    try:
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open(google_sheet_name)
        wks = sh.worksheet(unquote(sheet_name))
        data = wks.get_all_values()
        headers = None
        records = []

        for row in data:
            # print(set(row))
            if not headers:
                if any(word in row for word in ['SNO', 'Date', 'Client Name', 'Contact', 'Email', 'Project Name', 'Product']):
                    headers = row
            else:
                records.append(row)

        if not headers:
            print("Headers not found in any row.")
            return []
        
        # print(headers)
        return [headers, records]
    
    except GSpreadException as e:
        print("Error while attempting to find headers in subsequent rows:", e)
        return []
    # return render_template('sheets.html')

def add_sale():
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
    sh = gc.open(google_sheet_name)
    wks = sh.worksheet('Total Sales')
    wks.append_row(row_to_append)
    return 'success'
    # return redirect(url_for('employees'))
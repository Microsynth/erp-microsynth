# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
import socket

def print_raw(ip, port, content):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    s.send(content.encode())
    s.close()
    return
    
def print_test_label():
    content = """m m
J
H 100
S 0,-2.5,145,150,105.0
O R
B 1,3.5,0,DATAMATRIX,0.3;Pl00002877
T 6,3.5,0,3,pt 4;MGo
T 9,3.5,0,3,pt 4;2022-09-20, 13:05:26
T 1,9.5,0,3,pt 4;NGS02065
T 6,7.5,0,3,pt 4;Pool
T 6,5.5,0,3,pt 6;Pl00002877
T 11,9.5,0,3,pt 4;Pool-3 NGS01965
A 1
"""    
    print_raw('192.0.1.70', 9100, content )

def show_test_address_template():
    content = frappe.render_template("microsynth/templates/includes/address_label_brady.html", {'contact':'215856','address':'215856', 'customer':'8003'})
    print(content)

def print_test_address_template():
    content = frappe.render_template("microsynth/templates/includes/address_label_brady.html", {'contact':'215856','address':'215856', 'customer':'8003'})
    print_raw('192.0.1.70', 9100, content )

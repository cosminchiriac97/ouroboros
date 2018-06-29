import base64

a = b'asda[;dasd12312hjkbsadkjasnda'
a = base64.b64encode(a).decode()
print(a)
print (base64.b64decode(a.encode()))
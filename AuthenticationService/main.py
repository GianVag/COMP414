from flask import Flask, redirect, url_for, request, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
import jwt
import datetime
import json
from kazoo.client import KazooClient
import socket
import os

myip = socket.gethostbyname(socket.gethostname())
myport = '5000'

zk_url = 'localhost:2181'
zk = KazooClient(hosts=zk_url)
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    
    zk.start()
    my_zk_path = zk.create("services/auth/auth", str.encode("http://"+myip + ":" + myport), makepath=True, sequence=True, ephemeral=True)
    print(my_zk_path)
    # zk.set(my_zk_path,str.encode(myip+":"+myport))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql://test:123456@localhost/vsam"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'thisisatestkey'

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(12), unique=True)
    email = db.Column(db.String(30), unique=True)
    password = db.Column(db.String(100))
    auth_token = db.Column(db.String(300))
    role = db.Column(db.Integer, default=1)

    @property
    def serialize(self):
        """Return object data in easily serializable format"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role
        }

    def __init__(self, username, email, password, role):
        self.username = username
        self.email = email
        self.password = password
        self.auth_token = ''
        self.role = role

# Defining the home page of our site


@app.route("/")  # this sets the route to this page
def home():
    return jsonify(json_list=[r.serialize for r in User.query.all()])


@app.route("/login", methods=["POST"])
def login():
    form = request.form
    if form['username'] and form['password']:
        found_user = User.query.filter_by(username=form['username']).first()
        if found_user and check_password_hash(found_user.password, form['password']):
            token = jwt.encode({'user': form['username'], 'id': found_user.id, 'role': found_user.role, 'exp': datetime.datetime.now() + datetime.timedelta(minutes=30)}, app.config['SECRET_KEY'])
            found_user.auth_token = token
            db.session.commit()
            print(jwt.decode(token, 'thisisatestkey'))
            return make_response(jsonify({'token': token.decode(encoding='UTF-8')}))
    return make_response('Could not verify', 401)


@app.route("/register", methods=["POST"])
def register():
    form = request.form
    if User.query.filter_by(username=request.form['username']).first():
        return make_response('username already exists', 403)
    if User.query.filter_by(email=request.form['email']).first():
        return make_response('email already exists', 403)
    if form['username'] and form['password'] and form['email']:
        usr = User(form['username'], form['email'], generate_password_hash(form['password']), 1)
        db.session.add(usr)
        db.session.commit()
        return make_response('user added')
    else:
        return make_response('not enough data', 403)


if __name__ == "__main__":

    db.create_all()
    app.run(debug=True, host=myip, port=int(myport))

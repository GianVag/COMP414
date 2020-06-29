from flask import Flask, redirect, url_for, request, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
import requests
import jwt
import datetime
import json
from kazoo.client import KazooClient

zk = KazooClient(hosts='localhost:2181')
zk.start()
#zk.set("my/favorite/node", b"this is it")

active_plays = {}
game_id = 0

AuthenticationURI = 'http://127.0.0.1:5000'
GamemasterURI = 'http://127.0.0.1:5001'
UserInterfaceURI = 'http://127.0.0.1:5010'

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


@app.route("/zoo")
def zoo():
    data, stat = zk.get("my/favorite/node", watch=None)
    return data


@app.route("/zoo/<txt>")
def txt(txt):
    zk.set("my/favorite/node", bytes(txt, 'utf-8'))
    return "\"" + txt + "\"" + " was written"

# Defining the home page of our site


@app.route("/")  # this sets the route to this page
def home():
    return jsonify(json_list=[r.serialize for r in User.query.all()])


@app.route("/createPlay", methods=["POST"])
def createPlay():
    global active_plays, game_id
    form = request.form
    if int(form['game']) == 1:
        game_id += 1
        txt = form['player1'] + "; " + form['player2'] + "; " + form['game']
        print(max(active_plays.keys()) + 1 if bool(active_plays) else 1)
        game_data = {"player1": form["player1"], "player2": form["player2"], "game": max(active_plays.keys()) + 1 if bool(active_plays) else 1, "board": [[0, 0, 0], [0, 0, 0], [0, 0, 0]], "turn": 0, "winner": -1}
        active_plays[game_id] = game_data
        # print(max(active_plays.keys()))
        return jsonify(active_plays)
        zk.set("my/favorite/node", bytes(txt, 'utf-8'))
    return make_response('ok')


@app.route("/makeMove", methods=["POST"])
def makeMove():
    global active_plays
    form = request.form
    this_game = active_plays[int(form['game'])]

    if this_game['turn'] < 0:
        return make_response('This game is finished', 403)

    if (this_game["turn"] % 2 == 0 and form['id'] == this_game["player1"]) or (this_game["turn"] % 2 == 1 and form['id'] == this_game["player2"]):
        if this_game["board"][int(form['x'])][int(form['y'])] == 0:
            this_game["board"][int(form['x'])][int(form['y'])] = 1 if this_game['turn'] % 2 == 1 else -1
            this_game['turn'] += 1
            board = this_game["board"]
            if abs(board[0][0] + board[0][1] + board[0][2]) == 3:
                this_game['turn'] = -1
                this_game['winner'] = (this_game["turn"] - 1) % 2 + 1
            if abs(board[1][0] + board[1][1] + board[1][2]) == 3:
                this_game['turn'] = -1
                this_game['winner'] = (this_game["turn"] - 1) % 2 + 1
            if abs(board[2][0] + board[2][1] + board[2][2]) == 3:
                this_game['turn'] = -1
                this_game['winner'] = (this_game["turn"] - 1) % 2 + 1
            if abs(board[0][0] + board[1][0] + board[2][0]) == 3:
                this_game['turn'] = -1
                this_game['winner'] = (this_game["turn"] - 1) % 2 + 1
            if abs(board[0][1] + board[1][1] + board[2][1]) == 3:
                this_game['turn'] = -1
                this_game['winner'] = (this_game["turn"] - 1) % 2 + 1
            if abs(board[0][2] + board[1][2] + board[2][2]) == 3:
                this_game['turn'] = -1
                this_game['winner'] = (this_game["turn"] - 1) % 2 + 1
            if abs(board[0][0] + board[1][1] + board[2][2]) == 3:
                this_game['turn'] = -1
                this_game['winner'] = (this_game["turn"] - 1) % 2 + 1
            if abs(board[0][2] + board[1][1] + board[2][0]) == 3:
                this_game['turn'] = -1
                this_game['winner'] = (this_game["turn"] - 1) % 2 + 1
            if this_game['turn'] == 9:
                this_game['turn'] = -1
                this_game['winner'] = 0

            active_plays[int(form['game'])] = this_game
            if this_game['winner'] != -1:
                data = {}
                data['player1'] = this_game["player1"]
                data['player2'] = this_game["player2"]
                data['winner'] = this_game['winner']
                data['tournament'] = -1
                data['points1'] = 3 if this_game['winner'] == 1 else (0 if this_game['winner'] == 2 else 1)
                data['points2'] = 3 if this_game['winner'] == 2 else (0 if this_game['winner'] == 1 else 1)
                print(data)
                print(this_game)
                a = requests.post(GamemasterURI + "/gameFinished", data=data)
            return jsonify(active_plays[int(form['game'])])
        else:
            return make_response('Invalid position', 403)
    else:
        return make_response('Not your turn', 401)


@app.route("/playerActiveGames", methods=["POST"])
def playerActiveGames():
    global active_plays
    form = request.form
    id = form['id']
    tmp = {}
    for (k, v) in active_plays.items():
        if v['player1'] == form['id'] or v['player2'] == form['id']:
            print(v)
            tmp[k] = v
        else:
            print('not my game')
    return tmp


@app.route("/getGame", methods=["POST"])
def getGame():
    global active_plays
    form = request.form
    id = int(form['id'])
    if id in active_plays.keys():
        return make_response(active_plays[id])
    else:
        return make_response('invalid id', 403)


if __name__ == "__main__":
    db.create_all()
    app.run(debug=True, host='127.0.0.1', port=5003)

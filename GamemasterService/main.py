from flask import Flask, redirect, url_for, request, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests 
import pymysql
import jwt
import datetime
import json
from kazoo.client import KazooClient

zk = KazooClient(hosts='localhost:2181')
zk.start()
zk.ensure_path("my/Gamemaster/")
if zk.exists("my/Gamemaster/node"):
	data, stat = zk.get("my/Gamemaster/node", watch=None)
else:
	zk.create("my/Gamemaster/node", value=b"")

PlaymasterURI = 'http://127.0.0.1:5003'
waiting_list = []
waiting_list.append([])
waiting_list.append([])

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql://root:@localhost/vsam"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'thisisatestkey'

db = SQLAlchemy(app)

class Play(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	player1 = db.Column(db.Integer)
	player2 = db.Column(db.Integer)
	winner = db.Column(db.Integer)
	tournament = db.Column(db.Integer)
	points1 = db.Column(db.Integer)
	points2 = db.Column(db.Integer)

	def __init__(self, player1, player2, winner, tournament, points1, points2):
		self.player1 = player1
		self.player2 = player2
		self.winner = winner
		self.tournament = tournament
		self.points1 = points1
		self.points2 = points2

@app.route("/joinPractice", methods=["POST"])
def joinPractice():
	form = request.form
	print(waiting_list[int(form['game'])])
	if int(form['id']) in waiting_list[int(form['game'])]:
		return make_response('player already in waiting list', 403)
	if len(waiting_list[int(form['game'])]) > 0:
		other_player = waiting_list[int(form['game'])].pop()
		mydata = {"player1" : other_player, "player2" : form['id'], "game" : form['game']}
		a = requests.post(PlaymasterURI+"/createPlay", data = mydata)
		return a.text


	waiting_list[int(form['game'])].append(int(form['id']))
	return json.dumps('joined')

@app.route("/zoo/<txt>")
def txt(txt):
	zk.set("my/favorite/node", bytes(txt, 'utf-8'))
	return "\""+txt+"\""+" was written"


@app.route("/gameFinished", methods=["POST"])
def gameFinished():
	form = request.form
	player1 = form['player1']
	player2 = form['player2']
	winner = int(form['winner'])
	tournament = form['tournament']
	points1 = form['points1']
	points2 = form['points2']
	play = Play(player1, player2, winner, tournament, points1, points2)
	db.session.add(play)
	db.session.commit()
	play = Play(player2, player1, 1 if winner==2 else (2 if winner==1 else 0), tournament, points2, points1)
	db.session.add(play)
	db.session.commit()
	return make_response('play saved')
	


if __name__ == "__main__":
	db.create_all()
	app.run(debug=True, host='127.0.0.1', port=5001)
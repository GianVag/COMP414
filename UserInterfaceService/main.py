from flask import Flask, redirect, url_for, request, make_response, jsonify, render_template, session, flash
from flask_socketio import SocketIO, send, emit
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import jwt
import datetime
import json
from kazoo.client import KazooClient
import socket
import os


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
ip = s.getsockname()[0]
s.close()

myip = socket.gethostbyname(socket.gethostname())
myport = '5010'

zk_url = 'localhost:2181'
global zk
zk = KazooClient(hosts=zk_url)
zk.start()
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':

    my_zk_path = zk.create("services/ui/ui", str.encode(myip + ":" + myport), makepath=True, sequence=True, ephemeral=True)
    print(my_zk_path)
    # zk.set(my_zk_path,str.encode(myip+":"+myport))



active_plays = {}
game_id = 0
Users = {}
print("Waiting for Authentication Service")
while True:
    children = zk.get_children("/services/auth")
    if len(children) > 0:
        print("child found")
        data, stat = zk.get('/services/auth/' + children[0])
        AuthenticationURI = data.decode("utf-8")
        print("auth services url: "+AuthenticationURI)
        break
print("Waiting for Gamemaster Service")
while True:
    children = zk.get_children("/services/gmaster")
    if len(children) > 0:
        print("child found")
        data, stat = zk.get('//services/gmaster/' + children[0])
        GamemasterURI = data.decode("utf-8")
        print("game master url: "+GamemasterURI)
        break

PlaymasterURI = 'http://127.0.0.1:5003'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'thisisatestkey'

socketio = SocketIO(app)


# Defining the home page of our site


@app.route("/")  # this sets the route to this page
def home():
    return render_template('index.html', content="Home Page...")


@app.route("/games")
def games():
    if "username" in session:
        return render_template('games.html')
    else:
        flash("You have to login first")
        return redirect(url_for('login'))


@app.route("/Chess")
def chess():
    if "username" in session:
        return render_template('chess.html')
    else:
        flash("You have to login first")
        return redirect(url_for('login'))


@app.route("/TicTacToe")
def ticTacToe():
    if "username" in session:
        data = {'id': session['id']}
        # print(data)
        games = {}
        a = requests.post(PlaymasterURI + "/playerActiveGames", data=data)
        for (k, v) in json.loads(a.text).items():
            games[k] = v
        print(games)
        return render_template('ticTacToe.html', games=games)
    else:
        flash("You have to login first")
        return redirect(url_for('login'))


@app.route("/TicTacToe/<id>")
def ticTacToeGame(id):
    session['game'] = id
    data = {'id': id}
    a = requests.post(PlaymasterURI + "/getGame", data=data)
    if a.status_code == 200:
        board = json.loads(a.text)['board']
        return render_template('playTicTacToe.html', board=board)
    else:
        return make_response('invalid game id', 403)


@app.route("/TicTacToe/joinPractice", methods=["POST"])
def joinPracticeTicTacToe():
    if "username" in session:
        flash("You have joined the queue for Tic Tac Toe")
        return redirect(url_for("ticTacToe"))
    else:
        flash("You have to login first")
        return redirect(url_for('login'))


@app.route("/login", methods=["POST", "GET"])
def login():
    if "username" in session:
        return redirect(url_for('home'))
    if request.method == "GET":
        return render_template('login.html')
    form = request.form
    if request.method == "POST":
        mydata = {"username": form['username'], "password": form['password']}
        a = requests.post(AuthenticationURI + "/login", data=mydata)
        if a.status_code == 200:
            session.clear()
            session['username'] = form['username']
            session['token'] = json.loads(a.text)['token']
            session['id'] = jwt.decode(session['token'], 'thisisatestkey')['id']
            return redirect(url_for('home'))  # json.loads(a.text)['token']
        else:
            flash("Incorrect credentials, please try again.")
            return render_template('login.html')
        return a.text


@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    flash("You have logged out.")
    return redirect(url_for('home'))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "username" in session:
        return redirect(url_for('home'))
    if request.method == "GET":
        return render_template('register.html')
    if request.method == "POST":
        form = request.form
        mydata = {"email": form["email"], "username": form['username'], "password": form['password']}
        a = requests.post(AuthenticationURI + "/register", data=mydata)
        if a.status_code == 200:
            flash("You have successfully registered")
            flash("You can now login.")
            return redirect(url_for('login'))
        else:
            flash(a.text)
            return render_template('register.html')


@socketio.on('message')
def handleMessage(msg):
    print('Message: ' + msg)
    send(msg, broadcast=True)


@socketio.on('connected')
def handleConnected(payload):
    Users[payload] = request.sid
    print(Users)
    #send('testaaa', room=Users['vagelis'])


@socketio.on('joinPractice')
def handleJoinPractice(payload):
    data = payload
    print(data)
    a = requests.post(GamemasterURI + "/joinPractice", data=data)
    send(a.text)


@socketio.on('getPlays')
def getPlays(payload):
    data = payload
    print(data)
    a = requests.post(PlaymasterURI + "/playerActiveGames", data=data)
    send(a.text)


@socketio.on('makeMove')
def makeMove(payload):
    data = payload
    a = requests.post(PlaymasterURI + "/makeMove", data=data)
    if a.status_code == 200:
        # print(a.text)
        game = json.loads(a.text)
        # print(session['id'])
        this_player = str(session['id'])
        print(game['player1'])
        if this_player == game['player1']:
            other_player = game['player2']
        else:
            other_player = game['player1']
        if game['winner'] == -1:
            send('Move done')
        elif game['winner'] == 0:
            send('Draw!')
            emit('message', 'Draw!', Users[other_player])
        elif game['winner'] > 0:
            send('You are victorious!!!')
            emit('message', 'Better luck next time...', Users[other_player])
        emit('board', game['board'])
        emit('board', game['board'], Users[other_player])
    else:
        send(a.text)


if __name__ == "__main__":
    # db.create_all()
    socketio.run(app, debug=True, host=ip, port=5010)

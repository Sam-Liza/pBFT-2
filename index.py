# from flask import Flask
# import asyncio
# import websockets
# import json

# app = Flask(__name__)


# @app.route("/index")
# def hello():
# 	return "Hello World"


# # @app.route("/")
# async def connect_routine():
# 	uri = "ws://localhost:8765"
# 	async with websockets.connect(uri) as websocket:
# 		message = {'type': 'handshake', 
# 					'IpAddr': '127.0.0.1', 
# 					'port': 8000,
# 					'Uri': "Mydick"}
# 		message = json.dumps(message)
# 		await websocket.send(message)
# 		id_ = await websocket.recv()
# 		print(id_)
# 		print()
# 		return str(id_)

# @app.route("/")
# def connect():
# 	loop = asyncio.new_event_loop()
# 	asyncio.set_event_loop(loop)
# 	future = asyncio.ensure_future(connect_routine()) # tasks to do
# 	id_ = loop.run_until_complete(future)
# 	return str(id_)

# if __name__ == '__main__':
# 	app.run("0.0.0.0", 1234, debug=True)

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, emit, send
import asyncio
from multiprocessing import Process
import time
import json
import re
import os

from cluster import Cluster
import communication
import messaging
import sign

# initialize Flask
app = Flask(__name__)
socketio = SocketIO(app)
primary = False
ROOMS = {} # dict to track active rooms

port = 4003

ConnectedClients = {}
reply = {}
primary = None

public, private = sign.GenerateKeys(2048)
public, private = public.exportKey('PEM'), private.exportKey('PEM')


def Primary(ConnectedClients):
	for Client in ConnectedClients.values():
		if Client['primary']:
			return Client['Uri']

@app.route('/', methods=['GET', 'POST'])
def index():
    
	if request.method == 'GET':
		return render_template('home.html')
	if request.method == 'POST':

		print(request.form.get('nodes'))
		return render_template('index.html')


@app.route('/request_client', methods=['POST'])
def interactive():
	data = request.values
	num1 = data['n1']
	num2 = data['n2']
	oper = 'add'

	# Primary = ConnectedClients[0]
	primary = Primary(ConnectedClients)
	# print(ConnectedClients)
	print(primary)
	# socketio.emit

	message = {"o": oper,"args": {"num1": num1, "num2": num2}, "t": int(time.time()), "c": 1234567}
	message = messaging.jwt(json=message, header={"alg": "RSA"}, key=private)
	message = message.get_token()
	reply = communication.SendMsg(primary, json.dumps({'token': message, 'type': 'Request'}))
	# reply = await SendMsg(primary['Uri'], message)
	# return render_template('interactive.html')
	return render_template('index.html', num_nodes=len(ConnectedClients))

@socketio.on('create')
def on_create(data):
	# emit('join_room', {'room': "gaand"})
	print(data)
	if len(ConnectedClients):
		primary = False
	primary = True
	p = Process(target=Cluster, args=(int(data['nodes']), primary))
	p.start()
	# Cluster(data['nodes'])	

@socketio.on('client')
def on_connect(data):
	print('connect initialized')
	# print(data['clients_info'])
	ConnectedClients[data['id']] = data['clients_info']
	# primary = ConnectedClients[0]
	IpAddr = re.search(re.compile(r'(?<=inet )(.*)(?=\/)', re.M), os.popen('ip addr show wlp3s0').read()).groups()[0] 
	message = {'type': 'Client', 'client_id': 1234567890, 'public_key': public.decode('utf-8'), 'Uri': 'http://'+IpAddr+':'+str(port) }
	socketio.emit('clients', {'number': data['total_clients']})
	time.sleep(1)
	reply = communication.SendMsg(data['clients_info']['Uri'], message)
	# socketio.emit('log', {'no_clients': len(ConnectedClients), 'recv_client_info': ConnectedClients})

@socketio.on('check_clients')
def on_log(data):
	print("\n"*4)
	print("con Clients= ", ConnectedClients)
	print("\n"*4)

@socketio.on('reply')
def on_reply(data):
	print(data)
	jwt = messaging.jwt()
	token = jwt.get_payload(data['token'])
	print(token)
	if token['t'] in reply:
		if token['r'] == reply[token['t']]['r']:
			reply[token['t']]['count'] += 1
	else:
		reply[token['t']] = {'r': token['r'], 'count': 0}

	print(f"Count = {reply[token['t']]['count']}")
	if reply[token['t']]['count'] >= (len(ConnectedClients)//3) + 1:
		print("Socket emiting")
		socketio.emit('Reply', {'reply': reply[token['t']]['r'] })
		print("Socket emited")




if __name__ == '__main__':
    socketio.run(app, '0.0.0.0', port, debug=True)
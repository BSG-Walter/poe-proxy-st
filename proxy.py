from flask import Flask, request, jsonify
import websockets
import time
import poe
import sys
import time
import json

config=[]
config_path = "config.json"
with open(config_path, 'r') as config_file:
    config = json.load(config_file)

token = config['settings']['token']
client = poe.Client(token)

print("Lista de bots:")
print(json.dumps(client.bot_names, indent=2))

def jsonToText(message):
    result = []
    current_chunk = ""
    max_length = 4000
    
    for message in message['messages']:
        if message['role'] == "assistant" : message['role'] = config['replace']['assistant']
        if message['role'] == "user" : message['role'] = config['replace']['user']
        if message['role'] == "system" : message['role'] = config['replace']['system']
        msg = f"{message['role']}: {message['content']}\n\n"
        if len(current_chunk) + len(msg) <= max_length:
            current_chunk += msg
        else:
            result.append(current_chunk)
            current_chunk = msg
    
    if current_chunk:  # Si quedó algún trozo sin agregar
        result.append(current_chunk)

    return result

async def main():
  async with websockets.serve(websocket_handler, "localhost", 8765):
    await asyncio.Future()

app = Flask(__name__)

@app.route('/chat/completions', methods=['POST']) 
def completions():
    # Obtener el mensaje de la solicitud y partimos el prompt cada 4000 caracteres para que poe lo pueda procesar bien
    messages = jsonToText(request.get_json())
    response = ""

    for i in range(len(messages)):
        message = messages[i]

        if i == len(messages) - 1:
            for chunk in client.send_message(config['settings']['bot'], message):
                pass
            response = {
                "choices": [
                    {
                    "message": {
                        "role":"assistant",
                        "content": chunk["text"]
                    }
                    }
                ] 
            }
        else: 
            #estos son los primeros mensajes, se borran apenas se generan respuesta
            for chunk in client.send_message(config['settings']['bot'], message):
                client.purge_conversation(config['settings']['bot'], count=1)
                break

        print(message)

    return jsonify(response)

@app.route('/models', methods=['GET'])
def models():

    response = {
        "object": "list",
        "data": [
            {
                "id": "gpt-3.5",
                "object": "model",
                "created": time.time(), 
                "owned_by": "openai",
                "permission": [],
                "root": "gpt-3.5",
                "parent": None
            }
        ]
    }
    
    return jsonify(response)

if __name__ == '__main__':
  app.run(port=5000)
  asyncio.run(main())
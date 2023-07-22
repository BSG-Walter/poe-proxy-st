from flask import Flask, Response, request, jsonify
import time
import poe
import sys
import time
import json
import atexit

config=[]
config_path = "config.json"
aborted = False

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
    stream = request.get_json()['stream']

    if stream:
        return Response(event_stream(messages), content_type='text/event-stream')

    for i in range(len(messages)):
        message = messages[i]

        if i == len(messages) - 1:
            for chunk in client.send_message(config['settings']['bot'], message):
                pass
            chunk["text"]=chunk["text"].split("U:")[0].replace("A:","")
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

        #print(message)

    return jsonify(response)

def handle_abort(status = True):
    global aborted
    aborted = status

@app.teardown_request
def teardown_request(exception):
    if exception:
        handle_abort()

def event_stream(messages):

    response = {
        "choices": [{
            "delta": {
                "role":"assistant",
            }
        }]
    }
    yield '\n\ndata: ' + json.dumps(response)
    time.sleep(0.1)
    prev_chunk = ""

    for i in range(len(messages)):
        message = messages[i]

        if i == len(messages) - 1:
            for chunk in client.send_message(config['settings']['bot'], message):
                if aborted: #si le dan al boton stop, borramos el ultimo mensaje para cancelar la generacion (WIP)
                    print ("Mensaje cancelado")
                    client.purge_conversation(config['settings']['bot'], count=1)
                    handle_abort(False)
                    break

                chunk = chunk["text_new"] 
                if (chunk == ":" and prev_chunk == "U") : #esta intentando crear mensajes por nosotros, por ahora lo dejo asi pero probablemnte sea buena idea cancelar el mensaje
                    pass
                if chunk != "A" and not (chunk == ":" and prev_chunk == "A") : #evitamos enviar el A: que representa el inicio de mensajes de asistente.
                    response = {"choices": [{"delta": {"content": chunk}}] }
                    yield '\n\ndata: ' + json.dumps(response)
                prev_chunk = chunk

            yield '\n\ndata: [DONE]'
        else: 
            #estos son los primeros mensajes, se borran apenas se generan respuesta
            for chunk in client.send_message(config['settings']['bot'], message):
                client.purge_conversation(config['settings']['bot'], count=1)
                break

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
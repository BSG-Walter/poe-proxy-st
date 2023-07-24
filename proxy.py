from flask import Flask, Response, request, jsonify
import time
from async_poe_client import Poe_Client
import asyncio
import sys
import time
import json
import atexit

aborted = False

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
            chunk = await cliente.ask(url_botname=config['settings']['bot'], question=message, suggest_able=False):
            chunk = chunk.split("U:")[0].replace("A:","")
            response = {
                "choices": [
                    {
                    "message": {
                        "role":"assistant",
                        "content": chunk
                    }
                    }
                ] 
            }
        else: 
            #estos son los primeros mensajes, se borran apenas se generan respuesta
            async for chunk in cliente.ask_stream(url_botname=config['settings']['bot'], question=message, suggest_able=False):
                await cliente.delete_bot_conversation(url_botname=config['settings']['bot'], count=1)
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
        response = {"choices": [{"delta": {"content": ""}}]}
        if i == len(messages) - 1:
            async for chunk in cliente.ask_stream(url_botname=config['settings']['bot'], question=message, suggest_able=False):
                if aborted: #si le dan al boton stop, borramos el ultimo mensaje para cancelar la generacion (WIP)
                    print ("Mensaje cancelado")
                    await cliente.delete_bot_conversation(url_botname=config['settings']['bot'], count=1)
                    handle_abort(False)
                    break

                temp_chunk = prev_chunk + chunk

                if ("A:" in temp_chunk) or ("U:" in temp_chunk) or ("S:" in temp_chunk): #evitamos enviar el A: que representa el inicio de mensajes de asistente.
                    response["choices"][0]["delta"]["content"] = temp_chunk.replace("A:","").replace("U:", "").replace("S:","")
                    yield '\n\ndata: ' + json.dumps(response)
                    chunk = ""
                else:
                    response["choices"][0]["delta"]["content"] = prev_chunk
                    yield '\n\ndata: ' + json.dumps(response)

                if ("U:" in temp_chunk) : #esta intentando crear mensajes por nosotros, asi que cancelamos la generacion borrando el ultimo mensaje, y salimos del for
                    await cliente.delete_bot_conversation(url_botname=config['settings']['bot'], count=1)
                    prev_chunk = ""
                    break

                prev_chunk = chunk
            response["choices"][0]["delta"]["content"] = prev_chunk
            yield '\n\ndata: ' + json.dumps(response)
            time.sleep(0.2)
            yield '\n\ndata: [DONE]'
        else: 
            #estos son los primeros mensajes, se borran apenas se generan respuesta
            async for chunk in cliente.ask_stream(url_botname=config['settings']['bot'], question=message, suggest_able=False):
                cliente.purge_conversation(config['settings']['bot'], count=1)
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
    config=[]
    config_path = "config.json"

    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    if len(sys.argv) > 1:
        config['settings']['token'] = sys.argv[1]

    if len(sys.argv) > 2:
        config['settings']['bot'] = sys.argv[2]

    if len(sys.argv) > 3:
        config['settings']['formkey'] = sys.argv[3]
        
        with open(config_path, 'w') as config_file:
            json.dump(config, config_file)

    token = config['settings']['token']
    formkey = config['settings']['formkey']
    bot = config['settings']['bot']
    global cliente
    cliente = Poe_Client(token, formkey).create()

    bots = await poe_client.get_available_bots()
    print("Esta es tu lista de bots:\n")
    for bbot in bots:
        print(bbot['handle'])
    print("\nSi cambias al bot tienes que reiniciar esta celda para que el cambio surja efecto")

    print("\nTodo listo, Ya puedes conectarte a ST!\n")

    app.run(port=5000)
    asyncio.run(main())
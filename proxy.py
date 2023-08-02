from flask import Flask, Response, request, jsonify
import time
import poe
import sys
import time
import json
import atexit

aborted = False
connected = False

modelos = {
    "object": "list",
    "data": []
}

def add_model(new_id, new_root):
    modelos["data"].append({
        "id": new_id,
        "object": "model",
        "created": time.time(),
        "owned_by": "openai",
        "permission": [],
        "root": new_root,
        "parent": None
    })

#a sillytavern se envia la id para que aparezca en la lista de modelos, asi que decidi que en id va el nombre real y en root el identificador.
#esta mal pero asi se ve mejor en el front
def find_by_id(target_id):
    for model in modelos["data"]:
        if model.get("id") == target_id:
            return model
    return None

def dividirStr(str, size):
    return [str[i:i + size] for i in range(0, len(str), size)]

def jsonToText(message):
    result = []
    current_chunk = ""
    max_length = 5000
    
    for message in message['messages']:
        if message['role'] == "assistant" : message['role'] = config['replace']['assistant']
        if message['role'] == "user" : message['role'] = config['replace']['user']
        if message['role'] == "system" : message['role'] = config['replace']['system']
        msg = f"{message['role']}: {message['content']}\n\n"
        if len(current_chunk) + len(msg) <= max_length:
            current_chunk += msg
        else:
            if (len(msg) > max_length): #si en un solo mensaje hay mas de 5000 caracteres, partimos el mensaje en si.
                dividido = dividirStr(msg, max_length)
                result.extend(dividido[:-1])
                current_chunk = dividido[-1]
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

    model = find_by_id(request.get_json()['model'])
    if not model:
        print("No se encuentra el modelo especificado")
        return
    bot = model["root"]


    if stream:
        return Response(event_stream(messages, bot), content_type='text/event-stream')

    for i in range(len(messages)):
        message = messages[i]

        if i == len(messages) - 1:
            while(cliente.is_busy()):
                print(93)
                time.sleep(0.25)#esperamos hasta que el cliente se desocupe (que no se esten generando mensajes) hasta poder enviar otro mensaje
            for chunk in cliente.send_message(bot, message):
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
            while(cliente.is_busy()):
                print(111)
                time.sleep(0.25)#esperamos hasta que el cliente se desocupe (que no se esten generando mensajes) hasta poder enviar otro mensaje
            for chunk in cliente.send_message(bot, message):
                time.sleep(0.25)
                cliente.purge_conversation(bot, count=1)
                reconectar()
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

def event_stream(messages, bot):

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
            while(cliente.is_busy()):
                print(149)
                time.sleep(0.25)#esperamos hasta que el cliente se desocupe (que no se esten generando mensajes) hasta poder enviar otro mensaje
            for chunk in cliente.send_message(bot, message):
                if aborted: #si le dan al boton stop, borramos el ultimo mensaje para cancelar la generacion (WIP)
                    print ("Mensaje cancelado")
                    time.sleep(0.25)
                    cliente.purge_conversation(bot, count=1)
                    reconectar()
                    handle_abort(False)
                    break
                chunk = chunk["text_new"]
                temp_chunk = prev_chunk + chunk

                if ("A:" in temp_chunk) or ("U:" in temp_chunk) or ("S:" in temp_chunk): #evitamos enviar el A: que representa el inicio de mensajes de asistente.
                    response["choices"][0]["delta"]["content"] = temp_chunk.replace("A:","").replace("U:", "").replace("S:","")
                    yield '\n\ndata: ' + json.dumps(response)
                    chunk = ""
                else:
                    response["choices"][0]["delta"]["content"] = prev_chunk
                    yield '\n\ndata: ' + json.dumps(response)

                if ("U:" in temp_chunk) : #esta intentando crear mensajes por nosotros, asi que cancelamos la generacion borrando el ultimo mensaje, y salimos del for
                    cliente.purge_conversation(bot, count=1)
                    reconectar()
                    prev_chunk = ""
                    break

                prev_chunk = chunk
            response["choices"][0]["delta"]["content"] = prev_chunk
            yield '\n\ndata: ' + json.dumps(response)
            time.sleep(0.2)
            yield '\n\ndata: [DONE]'
        else: 
            #estos son los primeros mensajes, se borran apenas se generan respuesta
            while(cliente.is_busy()):
                print(182)
                time.sleep(0.25)#esperamos hasta que el cliente se desocupe (que no se esten generando mensajes) hasta poder enviar otro mensaje
            cant = 0
            for chunk in cliente.send_message(bot, message):
                time.sleep(0.25)
                cliente.purge_conversation(bot, count=1)
                reconectar()
                break

@app.route('/models', methods=['GET'])
def models():
    reconectar()
    return jsonify(modelos)

def reconectar():
    global cliente, connected
    if connected:
        connected = False
        cliente = poe.Client(config['settings']['token'], formkey=config['settings']['formkey'])
        connected = True
    return

if __name__ == '__main__':
    config=[]
    config_path = "config.json"

    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

    if len(sys.argv) > 1:
        config['settings']['token'] = sys.argv[1]

    if len(sys.argv) > 2:
        config['settings']['formkey'] = sys.argv[2]

    if len(sys.argv) > 3:
        config['settings']['bot'] = sys.argv[3]
        
        with open(config_path, 'w') as config_file:
            json.dump(config, config_file)

    global cliente
    cliente = poe.Client(config['settings']['token'], formkey=config['settings']['formkey'])
    connected = True

    print("Lista de bots:")
    #print(json.dumps(cliente.bot_names, indent=2))
    for modelid, modelname in cliente.bot_names.items():
        print(modelid + " - " + modelname)
        add_model(modelname, modelid)


    print("\n\nTodo listo, Ya puedes conectarte a ST!\n\n")

    app.run(port=5000)
    asyncio.run(main())